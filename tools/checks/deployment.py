"""The deployment manifests (`deploy/run/*.yaml`) carry no place, no credential and no rebuild.

Every value that differs per environment comes from the target (`# from-param:`), so no location
is written; the image is the placeholder the release replaces with a digest; a credential only
ever arrives by a secret reference; every variable set is a setting the service reads; no probe
path ends in `z` (the platform reserves some); each manifest reads one database login and the
three are different secrets; and the worker cannot scale to zero (a worker pool, or a service kept
at one instance with its CPU always on). Besides the service's own container, a manifest may hold
the metrics sidecar alone: named `collector`, the platform's image, no environment.
"""

import re
from pathlib import Path
from typing import Any

import yaml

from catalyst_ai.config import Settings
from tools.checks.gate import Violation

RUN = Path("deploy/run")
IMAGE = "catalyst-ai"
SIDECAR = "us-docker.pkg.dev/cloud-ops-agents-artifacts/cloud-run-gmp-sidecar/cloud-run-gmp-sidecar"
SIDECAR_NAME = "collector"
LOCATION = re.compile(r"\b(?:[a-z]+-){1,2}[a-z]+\d\b")
CREDENTIAL = re.compile(r"_(?:URL|PASSWORD|TOKEN|SECRET|KEY)$")
DATABASE = "_DATABASE_"
WORKER = "worker"
POOL = "WorkerPool"
PREFIX = "CATALYST_AI_"


def _containers(document: dict[str, Any]) -> list[dict[str, Any]]:
    spec: Any = document.get("spec", {})
    while isinstance(spec, dict) and "containers" not in spec:
        spec = (spec.get("template") or {}).get("spec", {})
    return list(spec.get("containers", [])) if isinstance(spec, dict) else []


def _is_sidecar(container: dict[str, Any]) -> bool:
    """Whether a container is the metrics sidecar: its name and its image, nothing else."""
    image = str(container.get("image", ""))
    named = container.get("name") == SIDECAR_NAME
    bare = image.split("@", maxsplit=1)[0].split(":", maxsplit=1)[0]
    return named and bare == SIDECAR and not container.get("env")


def _probe_paths(container: dict[str, Any]) -> list[str]:
    probes = [container.get(k) for k in ("startupProbe", "readinessProbe", "livenessProbe")]
    return [str(p["httpGet"]["path"]) for p in probes if isinstance(p, dict) and "httpGet" in p]


def known(name: str) -> bool:
    """Whether an environment variable is a setting the service reads."""
    field = name.removeprefix(PREFIX).lower()
    return name.startswith(PREFIX) and field in Settings.model_fields


def _env_problems(container: dict[str, Any]) -> tuple[list[str], list[str]]:
    problems, secrets = [], []
    for item in container.get("env") or []:
        name = str(item.get("name", ""))
        if not known(name):
            problems.append(f"{name} is not a setting the service reads")
        reference = (item.get("valueFrom") or {}).get("secretKeyRef")
        if CREDENTIAL.search(name) and reference is None:
            problems.append(f"{name} is not a secret reference")
        if DATABASE in name and reference is not None:
            secrets.append(str(reference.get("name")))
    return problems, secrets


def _worker_problem(name: str, document: dict[str, Any]) -> str | None:
    if WORKER not in name or document.get("kind") == POOL:
        return None
    template = (document.get("spec") or {}).get("template") or {}
    annotations = (template.get("metadata") or {}).get("annotations") or {}
    kept = str(annotations.get("autoscaling.knative.dev/minScale", "0")) not in {"0", ""}
    always = str(annotations.get("run.googleapis.com/cpu-throttling", "true")) == "false"
    return None if kept and always else "the worker can scale to zero"


def check(manifests: dict[str, str]) -> list[Violation]:
    """Report every rule a manifest breaks; the three database secrets must differ."""
    found: list[Violation] = []
    owners: dict[str, str] = {}
    for name, text in sorted(manifests.items()):
        found += [
            Violation(name, n, "a location is written")
            for n, line in enumerate(text.splitlines(), 1)
            if LOCATION.search(line.split("#")[0])
        ]
        document = yaml.safe_load(text) or {}
        worker = _worker_problem(name, document)
        found += [Violation(name, 1, worker)] if worker else []
        for container in _containers(document):
            if _is_sidecar(container):
                continue
            if container.get("image") != IMAGE:
                found.append(Violation(name, 1, f"the image is not the placeholder {IMAGE!r}"))
            found += [
                Violation(name, 1, f"probe {p} ends in z")
                for p in _probe_paths(container)
                if p.endswith("z")
            ]
            problems, secrets = _env_problems(container)
            found += [Violation(name, 1, p) for p in problems]
            if len(secrets) > 1:
                found.append(Violation(name, 1, "a process reads more than one database login"))
            for secret in secrets:
                if secret in owners:
                    found.append(Violation(name, 1, f"{secret} is also read by {owners[secret]}"))
                owners[secret] = name
    return found


def run(root: Path) -> list[Violation]:
    """Read every manifest under deploy/run."""
    folder = root / RUN
    paths = sorted(folder.glob("*.yaml")) if folder.is_dir() else []
    return check({str(RUN / p.name): p.read_text(encoding="utf-8") for p in paths})
