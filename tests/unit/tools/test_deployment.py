"""The deployment check: no location, no credential value, no rebuild, one login per process."""

from pathlib import Path

import yaml

from tools.checks import deployment

ROOT = Path(__file__).resolve().parents[3]


def service(env: str, *, image: str = "catalyst-ai", probe: str = "/health/live") -> str:
    return (
        "kind: Service\nspec:\n  template:\n    spec:\n      containers:\n"
        f"        - image: {image}\n          env:\n{env}"
        f"          livenessProbe:\n            httpGet:\n              path: {probe}\n"
    )


def secret(name: str, secret_name: str) -> str:
    return (
        f"            - name: {name}\n              valueFrom:\n                secretKeyRef:\n"
        f"                  name: {secret_name}\n                  key: latest\n"
    )


def plain(name: str, value: str) -> str:
    return f"            - name: {name}\n              value: {value}\n"


GOOD = service(
    plain("CATALYST_AI_PROVIDER_VERTEX_LOCATION", "set-by-target # from-param: ${loc}")
    + secret("CATALYST_AI_DATABASE_URL", "db-serve")
)


def messages(manifests: dict[str, str]) -> list[str]:
    return [v.message for v in deployment.check(manifests)]


def test_a_manifest_that_follows_every_rule_passes() -> None:
    assert messages({"deploy/run/api.yaml": GOOD}) == []


def test_a_written_location_is_refused_but_a_parameter_comment_is_not() -> None:
    written = service(plain("CATALYST_AI_PROVIDER_VERTEX_LOCATION", "us-central1"))
    assert messages({"deploy/run/api.yaml": written}) == ["a location is written"]


def test_a_credential_value_an_unknown_variable_and_a_rebuilt_image_are_refused() -> None:
    text = service(
        plain("CATALYST_AI_DATABASE_URL", "postgresql://u:p@h/d")
        + plain("CATALYST_AI_TYPO_ADDR", "x"),
        image="registry.example/catalyst-ai:latest",
    )
    assert messages({"deploy/run/api.yaml": text}) == [
        "the image is not the placeholder 'catalyst-ai'",
        "CATALYST_AI_DATABASE_URL is not a secret reference",
        "CATALYST_AI_TYPO_ADDR is not a setting the service reads",
    ]


def test_a_probe_path_ending_in_z_is_refused() -> None:
    assert messages({"deploy/run/api.yaml": service("", probe="/healthz")}) == [
        "probe /healthz ends in z"
    ]


def test_each_process_reads_one_login_and_no_two_share_one() -> None:
    both = service(
        secret("CATALYST_AI_DATABASE_URL", "db-serve")
        + secret("CATALYST_AI_DATABASE_MIGRATE_URL", "db-owner")
    )
    assert messages({"deploy/run/api.yaml": both}) == [
        "a process reads more than one database login"
    ]
    shared = service(secret("CATALYST_AI_DATABASE_WORKER_URL", "db-serve"))
    found = messages({"deploy/run/api.yaml": GOOD, "deploy/run/other.yaml": shared})
    assert found == ["db-serve is also read by deploy/run/api.yaml"]


def test_a_worker_service_must_keep_an_instance_with_its_cpu_on() -> None:
    assert messages({"deploy/run/worker.yaml": service("")}) == ["the worker can scale to zero"]
    kept = service("").replace(
        "  template:\n",
        "  template:\n    metadata:\n      annotations:\n"
        '        autoscaling.knative.dev/minScale: "1"\n'
        '        run.googleapis.com/cpu-throttling: "false"\n',
        1,
    )
    assert messages({"deploy/run/worker.yaml": kept}) == []


def test_the_repository_manifests_pass() -> None:
    assert deployment.run(ROOT) == []


SIDECAR = (
    "        - name: collector\n"
    "          image: us-docker.pkg.dev/cloud-ops-agents-artifacts/cloud-run-gmp-sidecar/"
    "cloud-run-gmp-sidecar:1.2.0\n"
)


def test_the_metrics_sidecar_is_allowed_and_nothing_dressed_as_it() -> None:
    assert messages({"deploy/run/api.yaml": GOOD + SIDECAR}) == []
    impostor = SIDECAR.replace("cloud-run-gmp-sidecar:1.2.0", "other:latest")
    assert messages({"deploy/run/api.yaml": GOOD + impostor}) == [
        "the image is not the placeholder 'catalyst-ai'"
    ]
    carrying = SIDECAR + "          env:\n" + plain("CATALYST_AI_LOG_LEVEL", "INFO")
    assert messages({"deploy/run/api.yaml": GOOD + carrying}) == [
        "the image is not the placeholder 'catalyst-ai'"
    ]


def test_the_scrape_config_reads_the_ops_port_metrics() -> None:
    config = yaml.safe_load((ROOT / "deploy/monitoring/run-gmp.yaml").read_text(encoding="utf-8"))
    assert config["kind"] == "RunMonitoring"
    assert config["spec"]["endpoints"] == [{"port": 9091, "path": "/metrics", "interval": "30s"}]
