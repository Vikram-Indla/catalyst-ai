"""The release: built once, pushed, named after its commit, pointing the manifests at a digest."""

from pathlib import Path

import pytest

from tools import release

COMMIT = "a" * 40
ENV = {"RELEASE_REGISTRY": "registry.example/catalyst/", "RELEASE_LOCATION": "set-by-environment"}


def test_the_release_is_named_after_the_commit_and_the_tag_carries_it() -> None:
    found = release.release_of(ENV, COMMIT)
    assert found.name == f"catalyst-ai-{COMMIT}"
    assert found.tag == f"registry.example/catalyst/catalyst-ai:{COMMIT}"


def test_the_place_is_configuration_and_the_commit_is_whole() -> None:
    with pytest.raises(release.ReleaseRefusedError, match="RELEASE_LOCATION must be set"):
        release.release_of({"RELEASE_REGISTRY": "r"}, COMMIT)
    with pytest.raises(release.ReleaseRefusedError, match="not a full commit id"):
        release.release_of(ENV, "abc123")


def test_the_steps_build_once_push_read_the_digest_then_create_the_release() -> None:
    target = release.release_of(ENV, COMMIT)
    ran: list[list[str]] = []
    digest = f"registry.example/catalyst/catalyst-ai@sha256:{'b' * 64}"

    def runner(command: list[str]) -> str:
        ran.append(command)
        return digest if command[:2] == ["docker", "inspect"] else ""

    assert release.run_release(target, runner, dry=False) == digest
    assert [c[:2] for c in ran] == [
        ["docker", "build"],
        ["docker", "push"],
        ["docker", "inspect"],
        ["gcloud", "deploy"],
        ["gcloud", "deploy"],
    ]
    assert ran[3][4] == f"catalyst-ai-migrate-{COMMIT}"
    assert "--skaffold-file=skaffold-migrate.yaml" in ran[3]
    assert "--delivery-pipeline=catalyst-ai-migrate" in ran[3]
    assert f"--images=catalyst-ai={digest}" in ran[3]
    assert f"org.opencontainers.image.revision={COMMIT}" in ran[0]
    assert ran[4][4] == f"catalyst-ai-{COMMIT}"
    assert f"--images=catalyst-ai={digest}" in ran[4]
    assert "--region=set-by-environment" in ran[4]


def test_a_tag_instead_of_a_digest_stops_the_release_before_it_is_created() -> None:
    target = release.release_of(ENV, COMMIT)
    ran: list[list[str]] = []

    def runner(command: list[str]) -> str:
        ran.append(command)
        return target.tag if command[:2] == ["docker", "inspect"] else ""

    with pytest.raises(release.ReleaseRefusedError, match="not a digest"):
        release.run_release(target, runner, dry=False)
    assert all(c[0] != "gcloud" for c in ran)


def test_print_runs_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    def runner(command: list[str]) -> str:
        raise AssertionError(command)

    release.run_release(release.release_of(ENV, COMMIT), runner, dry=True)
    printed = capsys.readouterr().out
    assert "docker build" in printed
    assert "gcloud deploy releases create" in printed


HOSTED = {
    **ENV,
    "ACTIONS_ID_TOKEN_REQUEST_URL": "https://token.example/request?x=1",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "s3cr3t-request",
    "RELEASE_WIF_PROVIDER": "projects/1/locations/global/workloadIdentityPools/p/providers/gh",
    "RELEASE_SERVICE_ACCOUNT": "release@delivery.example",
    "RUNNER_TEMP": "runner-temp",
}


def test_a_workstation_logs_in_itself_and_the_hosted_job_logs_in_first() -> None:
    target = release.release_of(ENV, COMMIT)
    assert release.login(ENV, target) == []
    steps = release.login(HOSTED, target)
    assert [s[:3] for s in steps] == [
        ["gcloud", "iam", "workload-identity-pools"],
        ["gcloud", "auth", "login"],
        ["gcloud", "auth", "configure-docker"],
    ]
    config = steps[0]
    assert config[4] == HOSTED["RELEASE_WIF_PROVIDER"]
    assert "--credential-source-type=json" in config
    assert "--credential-source-field-name=value" in config
    assert "--credential-source-headers=Authorization=Bearer s3cr3t-request" in config
    assert steps[1][-1] == f"--cred-file={Path('runner-temp') / 'gcloud-credentials.json'}"
    assert steps[2][3] == "registry.example"


def test_the_hosted_login_needs_its_settings() -> None:
    target = release.release_of(ENV, COMMIT)
    partial = {k: v for k, v in HOSTED.items() if k != "RELEASE_SERVICE_ACCOUNT"}
    with pytest.raises(release.ReleaseRefusedError, match="RELEASE_SERVICE_ACCOUNT"):
        release.login(partial, target)


def test_the_request_token_is_never_printed(capsys: pytest.CaptureFixture[str]) -> None:
    def runner(command: list[str]) -> str:
        raise AssertionError(command)

    target = release.release_of(ENV, COMMIT)
    release.run_release(target, runner, dry=True, environ=HOSTED)
    printed = capsys.readouterr().out
    assert "s3cr3t-request" not in printed
    assert "Bearer <request-token>" in printed
    assert printed.index("create-cred-config") < printed.index("docker build")
