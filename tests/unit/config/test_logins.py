"""Three logins outside development: required, and three different users."""

import re
from pathlib import Path

import pytest

from catalyst_ai.config.logins import logins_problem, named_after_itself, user_of

SERVE = "postgresql://catalyst_ai_serve@db/catalyst_ai"
WORKER = "postgresql://catalyst_ai_worker@db/catalyst_ai"
OWNER = "postgresql://catalyst_ai_owner@db/catalyst_ai"


def test_three_different_users_pass_and_development_is_not_bound() -> None:
    assert logins_problem(True, SERVE, WORKER, OWNER) is None
    assert logins_problem(False, SERVE, None, None) is None
    assert user_of(SERVE) == "catalyst_ai_serve"


@pytest.mark.parametrize(
    ("worker", "owner", "reason"),
    [
        (None, OWNER, "required"),
        (WORKER, None, "required"),
        (SERVE, OWNER, "three different users"),
        (WORKER, SERVE, "three different users"),
        ("postgresql://db/catalyst_ai", OWNER, "three different users"),
    ],
    ids=["no worker", "no owner", "worker is serve", "owner is serve", "worker names no user"],
)
def test_a_deployed_process_sharing_a_login_is_refused(
    worker: str | None, owner: str | None, reason: str
) -> None:
    problem = logins_problem(True, SERVE, worker, owner)
    assert problem is not None
    assert reason in problem


@pytest.mark.parametrize("which", ["serve", "worker", "owner"])
def test_a_development_password_is_refused_outside_development(which: str) -> None:
    urls = {"serve": SERVE, "worker": WORKER, "owner": OWNER}
    user = user_of(urls[which])
    urls[which] = urls[which].replace(f"//{user}@", f"//{user}:{user}@")
    problem = logins_problem(True, urls["serve"], urls["worker"], urls["owner"])
    assert problem is not None
    assert "development login" in problem
    assert logins_problem(False, urls["serve"], urls["worker"], urls["owner"]) is None


def test_the_compose_file_logins_are_all_development_logins() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    urls = re.findall(r"postgresql://\S+", compose)
    assert len(urls) == 3
    assert all(named_after_itself(url) for url in urls)
