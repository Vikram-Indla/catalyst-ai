"""`docker compose up` migrates before it serves, with the image that serves."""

import re
from pathlib import Path

import yaml

from tools import rules

COMPOSE = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))
SERVICES = COMPOSE["services"]
RUNTIME_STAGE = rules.DOCKERFILE.read_text(encoding="utf-8").split(" AS runtime", 1)[1]


def test_a_one_shot_migrate_service_runs_before_the_service_serves() -> None:
    migrate = SERVICES["migrate"]
    assert migrate["command"] == ["migrate"]
    assert migrate["depends_on"] == {"db": {"condition": "service_healthy"}}
    assert SERVICES["ai"]["depends_on"]["migrate"] == {
        "condition": "service_completed_successfully"
    }


def test_the_migrations_run_with_the_image_and_database_the_service_uses() -> None:
    migrate, ai = SERVICES["migrate"], SERVICES["ai"]
    assert migrate["build"] == ai["build"]
    assert migrate["image"] == ai["image"]
    assert migrate["environment"] == ai["environment"]
    assert migrate["env_file"] == ai["env_file"]


def test_the_runtime_image_carries_the_migrations_where_migrate_reads_them() -> None:
    assert re.search(r"^COPY db/migrations \./db/migrations$", RUNTIME_STAGE, re.M)
    assert re.search(r"^WORKDIR /app$", RUNTIME_STAGE, re.M)


def test_the_database_is_the_pinned_image() -> None:
    assert SERVICES["db"]["image"] == rules.CI_DATABASE_IMAGE
