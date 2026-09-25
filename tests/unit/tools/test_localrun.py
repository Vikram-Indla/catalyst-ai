"""The local-run check: no secret value in the example, every published port on loopback."""

from pathlib import Path

from tools.checks import localrun
from tools.checks.gitinfo import git_output

ROOT = Path(__file__).resolve().parents[3]


def test_a_secret_shaped_key_with_a_value_is_refused_commented_or_not() -> None:
    text = "\n".join(
        [
            "CATALYST_AI_DB_PASSWORD=" + "hunter2",
            "# CATALYST_AI_PROVIDER_ACCESS_TOKEN=" + "ya29.x",
            "CATALYST_AI_SIGNING_KEY=",
            "CATALYST_AI_WEBHOOK_SECRET=  ",
            "CATALYST_AI_LOG_LEVEL=INFO",
        ]
    )
    found = localrun.env_violations(text, "w")
    assert [(v.line, v.message.split(" ")[0]) for v in found] == [
        (1, "CATALYST_AI_DB_PASSWORD"),
        (2, "CATALYST_AI_PROVIDER_ACCESS_TOKEN"),
    ]


def test_only_a_named_public_key_may_carry_a_value() -> None:
    allowed = "CATALYST_AI_AUTH_PUBLIC_KEYS=test-1:abc"
    assert localrun.env_violations(allowed, "w") == []
    other = "CATALYST_AI_OTHER_PUBLIC_KEYS=test-1:abc"
    assert len(localrun.env_violations(other, "w")) == 1


def test_a_port_not_on_loopback_or_outside_the_agreed_set_is_refused() -> None:
    text = "\n".join(
        [
            "    ports:",
            '      - "5433:5432"',
            '      - "0.0.0.0:8090:8090"',
            '      - "127.0.0.1:5433:5432"',
            '      - "127.0.0.1:5434:5432"',
            '      - "127.0.0.1:9092:9091"',
        ]
    )
    found = localrun.port_violations(text, "w")
    assert [v.line for v in found] == [2, 3, 4]
    assert "not one the local run uses" in found[2].message


def test_the_repository_files_pass() -> None:
    assert localrun.run(ROOT) == []


def test_mains_compose_file_published_the_database_on_every_interface() -> None:
    before = git_output(ROOT, "show", "main:docker-compose.yml")
    if before is None or "127.0.0.1:5434" in before:
        return
    assert localrun.port_violations(before, "main") != []
