"""RULE-006 §1 step 4: every check is proven red on a planted violation, one line per check."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from tools.checks import (
    alerts,
    budgets,
    change_map,
    changelog,
    ci,
    ci_image_job,
    commitclass,
    commits,
    commitsize,
    coverage,
    deployment,
    deprecations,
    deps,
    evals,
    flags,
    gate,
    gitmount,
    images,
    invariants,
    journeys,
    latency,
    licenses,
    localrun,
    nightly_job,
    openapi,
    prclass,
    release_job,
    residency,
    sessions,
    vocabulary,
)
from tools.checks.gate import Violation
from tools.checks.gitinfo import Commit

PLANTS = Path(__file__).parent / "plants"
BAD_MANIFEST = (
    "kind: Service\nspec:\n  template:\n    spec:\n      containers:\n"
    "        - image: registry/catalyst-ai:latest\n          env:\n"
    "            - name: CATALYST_AI_PROVIDER_VERTEX_LOCATION\n              value: us-central1\n"
    "            - name: CATALYST_AI_DATABASE_URL\n              value: postgresql://u:p@h/d\n"
    "          livenessProbe:\n            httpGet:\n              path: /healthz\n"
)
FAR_PAST = date(2020, 1, 1)
LOW_COVERAGE = {
    "files": {"src/catalyst_ai/config/a.py": {"summary": {"percent_covered": 50.0}}},
    "totals": {"percent_covered": 50.0},
}
DEPRECATED_DOCUMENT = {"paths": {"/v1/old": {"post": {"deprecated": True}}}}
BAD_ALERTS = {
    "groups": [
        {
            "rules": [
                {"alert": "NoRunbook", "annotations": {}},
                {"alert": "Missing", "annotations": {"runbook": "docs/06-runbooks/nope.md"}},
            ]
        }
    ]
}
BAD_LATENCY = {
    "groups": [
        {
            "rules": [
                {
                    "alert": "OneForAll",
                    "expr": "histogram_quantile(0.95, rate("
                    + latency.REQUEST_SERIES
                    + '{operation=~".*"}[1h])) > 8',
                }
            ]
        }
    ]
}
BAD_REGISTRY = "| INV-001 | x | o | `tools/checks/nope` | C | S |"

VALUE_PLANTS: dict[str, Callable[[], list[Violation]]] = {
    "openapi": lambda: (
        openapi.drift_violations({"a": 1}, {"a": 2}, "w")
        + openapi.operation_violations({"paths": {"/x": {"get": {}}}}, "w")
    ),
    "changelog": lambda: changelog.check(["api/openapi.yaml"]),
    "deps": lambda: deps.check({"leftpad"}, set()),
    "licenses": lambda: licenses.check([("evil", "AGPL-3.0")]),
    "ci": lambda: (
        ci.check("      - run: echo hi\n", "w")
        + ci_image_job.check({"on": {}, "jobs": {}}, "      - run: echo hi\n", "w")
        + nightly_job.check({"on": {}, "jobs": {}}, "      - run: echo hi\n", "w", {})
        + release_job.check({"on": {}, "jobs": {}}, "      - run: echo hi\n", "w")
    ),
    "images": lambda: (
        images.check("FROM python:3.12\n", "CI_IMAGE := python:3.12\n", "")
        + images.setup_violations("RUN apt-get install -y make\n", "apt-get install -y make git")
        + images.pin_violations("a" * 64, "b" * 64, "c" * 64)
        + images.ci_image_violations("COPY . /src\n", "0")
    ),
    "commits": lambda: commits.check(
        [Commit("abc123def456", "x", ("uv.lock", "src/catalyst_ai/x.py"))]
    ),
    "sessions": lambda: sessions.check(["src/catalyst_ai/x.py"], {}),
    "prclass": lambda: prclass.check(
        ["src/catalyst_ai/contract/envelopes.py"], {"r.md": "Blast radius: LOCAL", "s.md": "x"}
    ),
    "commitclass": lambda: commitclass.check(
        ["tools/checks/x.py", "src/catalyst_ai/config/x.py"], {"r.md": "Blast radius: LOCAL"}
    ),
    "commitsize": lambda: commitsize.check(
        [commitsize.Staged("src/catalyst_ai/x.py", 401), commitsize.Staged("uv.lock", 900)],
        {"r.md": "**Ticket:** AI-001 · x", "s.md": "**Ticket:** AI-002 · y"},
        "gen: a mixed commit\n\nwith a body\n",
    ),
    "localrun": lambda: (
        localrun.env_violations("DB_PASSWORD=" + "hunter2\n# API_TOKEN=abc\n", "w")
        + localrun.port_violations('    ports:\n      - "5433:5432"\n', "w")
    ),
    "gitmount": lambda: gitmount.check('docker run -v "$(G)":/gitcommon -e GIT_DIR=x img\n', "w"),
    "deployment": lambda: deployment.check({"deploy/run/w.yaml": BAD_MANIFEST}),
    "invariants": lambda: invariants.check(BAD_REGISTRY, set(), set(), "w"),
    "evals": lambda: (
        [Violation("w", 1, k) for k in evals.loosened({"a": 0.8}, {"a": 0.7}, "a: 0.7")]
        + evals.set_violations([], "w")
    ),
    "budgets": lambda: budgets.check({"p95_latency_ms": 100}, {"p95_latency_ms": 200.0}, "w"),
    "deprecations": lambda: deprecations.check(DEPRECATED_DOCUMENT, FAR_PAST, "w"),
    "flags": lambda: flags.check(
        'x = Field(description="FLAG · AI-001 · 2020-01-01")', date(2026, 1, 1), "w"
    ),
    "journeys": lambda: journeys.check({"foo.run": ["ai.x.y"]}, set(), ""),
    "coverage": lambda: coverage.check(LOW_COVERAGE),
    "alerts": lambda: (
        alerts.alert_violations(BAD_ALERTS, {"capabilities.md"}, "w")
        + alerts.coverage_violations(BAD_ALERTS, "", {"orphan.md"})
        + alerts.about_violations(BAD_ALERTS, {"nope.md": "# A page about something else"})
    ),
    "latency": lambda: latency.check(
        {"improve_story.run": 4000},
        latency.latency_rules(BAD_LATENCY, latency.REQUEST_SERIES, "operation"),
        {8.0},
        "w",
    ),
    "change_map": lambda: change_map.check(
        ["notes.txt"], (("*", "docs"),), {"tests/t.py": {"docs/01-architecture/x.md"}}
    ),
    "residency": lambda: (
        residency.host_violations(
            "https://generative" + "language.googleapis.com", "w", frozenset({"x-1"})
        )
        + residency.kept_violations({})
    ),
    "vocabulary": lambda: vocabulary.check_lines(
        ["decided under " + "CA" + "T-0" + "07" + " by " + "il" + "ya-go"], "w"
    ),
}


def prove(name: str) -> tuple[bool, int]:
    """Run one check on its plant; red is the pass."""
    if name in VALUE_PLANTS:
        found = VALUE_PLANTS[name]()
    else:
        plant = PLANTS / name
        if not plant.is_dir():
            return False, 0
        found = gate.run_check(name, plant)
    return bool(found), len(found)


def main() -> int:
    """Prove every check red on its plant and print one line per check."""
    failures = 0
    for name in gate.CHECKS:
        red, count = prove(name)
        print(f"{'red ' if red else 'NOT RED'} {name} ({count} on plant)")
        failures += 0 if red else 1
    print(f"selftest: {len(gate.CHECKS) - failures}/{len(gate.CHECKS)} checks red on their plant")
    return 1 if failures else 0
