"""`make release`: the runtime image built once, pushed, and releases that name it by digest.

The steps, each printed before it runs, and with `--print` only printed: build the runtime image
labelled with its commit, push it, read back the digest the registry holds, and create two
releases named after the commit from that one digest — the migration's pipeline first (its
postdeploy action runs the job), then the service's — each pointing the manifests' placeholder
image at the digest. The lead promotes them in that order. Nothing is rebuilt downstream: the
digest is what moves. Where it goes is configuration: `RELEASE_REGISTRY` (the image repository)
and `RELEASE_LOCATION` (the pipelines' location) come from the environment, never from the repo.

Who runs it logs in as themselves on a workstation. In the hosted job (GitHub's OIDC variables
present) the login comes first and uses no action: a workload identity federation credential file
whose source is the job's own token URL, then `gcloud auth login --cred-file` and the registry's
docker login. The request token is never printed.
"""

import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

PIPELINE = "catalyst-ai"
MIGRATE_PIPELINE = "catalyst-ai-migrate"
IMAGE = "catalyst-ai"
REVISION_LABEL = "org.opencontainers.image.revision"
COMMIT = re.compile(r"^[0-9a-f]{40}$")
REQUIRED = ("RELEASE_REGISTRY", "RELEASE_LOCATION")
PRINT = "--print"
OIDC_URL_VARIABLE = "ACTIONS_ID_TOKEN_REQUEST_URL"
OIDC_REQUEST_VARIABLE = "ACTIONS_ID_TOKEN_REQUEST_TOKEN"
HOSTED = ("RELEASE_WIF_PROVIDER", "RELEASE_SERVICE_ACCOUNT")
MASK = "<request-token>"
CREDENTIALS = "gcloud-credentials.json"

Runner = Callable[[list[str]], str]


class ReleaseRefusedError(Exception):
    """A release that must not go ahead, and why."""


@dataclass(frozen=True)
class Release:
    """Where the image goes, where the release is created, and the commit both are named after."""

    registry: str
    location: str
    commit: str

    @property
    def tag(self) -> str:
        """Return the pushed tag: the image repository, the image, the commit."""
        return f"{self.registry}/{IMAGE}:{self.commit}"

    @property
    def migrate_name(self) -> str:
        """Return the migration release's name: its pipeline and the commit."""
        return f"{MIGRATE_PIPELINE}-{self.commit}"

    @property
    def name(self) -> str:
        """Return the release's name: the pipeline and the commit."""
        return f"{PIPELINE}-{self.commit}"


def release_of(environ: Mapping[str, str], commit: str) -> Release:
    """Return the release the environment and the commit describe, or refuse what is missing."""
    missing = [name for name in REQUIRED if not environ.get(name)]
    if missing:
        message = f"{', '.join(missing)} must be set (configuration, not the repo)"
        raise ReleaseRefusedError(message)
    if not COMMIT.match(commit):
        message = f"{commit!r} is not a full commit id"
        raise ReleaseRefusedError(message)
    return Release(environ["RELEASE_REGISTRY"].rstrip("/"), environ["RELEASE_LOCATION"], commit)


def build_and_push(release: Release) -> list[list[str]]:
    """Return the commands that build the image once, label it with its commit and push it."""
    return [
        [
            "docker",
            "build",
            "--label",
            f"{REVISION_LABEL}={release.commit}",
            "-t",
            release.tag,
            ".",
        ],
        ["docker", "push", release.tag],
    ]


def digest_query(release: Release) -> list[str]:
    """Return the command that reads the digest the registry holds for the pushed tag."""
    return ["docker", "inspect", "--format", "{{index .RepoDigests 0}}", release.tag]


def create_releases(release: Release, digest: str) -> list[list[str]]:
    """Return the two releases from one digest: the migration's first, then the service's."""
    shared = [f"--region={release.location}", "--source=deploy", f"--images={IMAGE}={digest}"]
    return [
        ["gcloud", "deploy", "releases", "create", release.migrate_name,
         f"--delivery-pipeline={MIGRATE_PIPELINE}", "--skaffold-file=skaffold-migrate.yaml",
         *shared],
        ["gcloud", "deploy", "releases", "create", release.name,
         f"--delivery-pipeline={PIPELINE}", "--skaffold-file=skaffold.yaml", *shared],
    ]  # fmt: skip


def login(environ: Mapping[str, str], release: Release) -> list[list[str]]:
    """Return the hosted job's login, or nothing outside it (a workstation uses its own login)."""
    if not environ.get(OIDC_URL_VARIABLE):
        return []
    missing = [name for name in HOSTED if not environ.get(name)]
    if missing:
        message = f"{', '.join(missing)} must be set for the hosted login"
        raise ReleaseRefusedError(message)
    provider = environ["RELEASE_WIF_PROVIDER"]
    credentials = str(Path(environ.get("RUNNER_TEMP", ".")) / CREDENTIALS)
    source = f"{environ[OIDC_URL_VARIABLE]}&audience=//iam.googleapis.com/{provider}"
    request = environ.get(OIDC_REQUEST_VARIABLE, "")
    return [
        [
            "gcloud", "iam", "workload-identity-pools", "create-cred-config", provider,
            f"--service-account={environ['RELEASE_SERVICE_ACCOUNT']}",
            f"--credential-source-url={source}",
            f"--credential-source-headers=Authorization=Bearer {request}",
            "--credential-source-type=json",
            "--credential-source-field-name=value",
            f"--output-file={credentials}",
        ],
        ["gcloud", "auth", "login", f"--cred-file={credentials}"],
        ["gcloud", "auth", "configure-docker", release.registry.split("/")[0], "--quiet"],
    ]  # fmt: skip


def shown(command: list[str], environ: Mapping[str, str]) -> str:
    """Return the command as printed: the job's request token masked."""
    text = " ".join(command)
    token = environ.get(OIDC_REQUEST_VARIABLE)
    return text.replace(token, MASK) if token else text


def run_command(command: list[str]) -> str:
    """Run one command, stop the release on a failure, and return what it printed."""
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()


def run_release(
    release: Release, runner: Runner, *, dry: bool, environ: Mapping[str, str] | None = None
) -> str:
    """Take the steps in order — the hosted login first — and return the digest it names."""
    env = environ or {}
    for command in [*login(env, release), *build_and_push(release)]:
        print("release:", shown(command, env))
        if not dry:
            runner(command)
    print("release:", " ".join(digest_query(release)))
    digest = f"{release.registry}/{IMAGE}@sha256:<digest>" if dry else runner(digest_query(release))
    if not digest.startswith(f"{release.registry}/{IMAGE}@sha256:"):
        message = f"the registry returned {digest!r}, not a digest of the image"
        raise ReleaseRefusedError(message)
    for command in create_releases(release, digest):
        print("release:", " ".join(command))
        if not dry:
            runner(command)
    return digest


def main(argv: list[str]) -> int:
    """Release the checked-out commit; `--print` shows the steps and runs none."""
    commit = run_command(["git", "rev-parse", "HEAD"])
    try:
        target = release_of(os.environ, commit)
        run_release(target, run_command, dry=PRINT in argv, environ=os.environ)
    except ReleaseRefusedError as refused:
        print(f"release: {refused}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
