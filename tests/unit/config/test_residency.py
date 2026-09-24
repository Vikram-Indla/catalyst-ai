"""Residency: the region is configuration from an in-Kingdom allowlist; deployed, it is required."""

import pytest

from catalyst_ai.config.residency import (
    DEVELOPMENT_LOCATION,
    IN_KINGDOM_LOCATIONS,
    regional_endpoint,
    residency_problem,
)

PROJECT = "catalyst-ai-test"
LOCATION = DEVELOPMENT_LOCATION


def test_the_endpoint_is_built_from_the_location() -> None:
    assert LOCATION in IN_KINGDOM_LOCATIONS
    assert regional_endpoint(LOCATION) == f"https://{LOCATION}-aiplatform.googleapis.com"


def test_a_deployed_process_in_an_allowed_location_passes() -> None:
    assert residency_problem(True, LOCATION, None, PROJECT, developer_token=False) is None
    origin = regional_endpoint(LOCATION) + "/"
    assert residency_problem(True, LOCATION, origin, PROJECT, developer_token=False) is None


@pytest.mark.parametrize(
    ("location", "origin", "project", "developer_token", "reason"),
    [
        (None, None, PROJECT, False, "PROVIDER_VERTEX_LOCATION is required"),
        (LOCATION, "https://aiplatform.googleapis.com", PROJECT, False, "regional endpoint"),
        (LOCATION, None, "", False, "PROVIDER_VERTEX_PROJECT"),
        (LOCATION, None, PROJECT, True, "workload identity"),
    ],
    ids=["no location", "other origin", "no project", "developer token"],
)
def test_a_deployed_process_elsewhere_is_refused(
    location: str | None, origin: str | None, project: str, developer_token: bool, reason: str
) -> None:
    problem = residency_problem(True, location, origin, project, developer_token)
    assert problem is not None
    assert reason in problem


@pytest.mark.parametrize("deployed", [True, False], ids=["deployed", "development"])
def test_a_location_outside_the_kingdom_is_refused_everywhere(deployed: bool) -> None:
    problem = residency_problem(deployed, "us-central1", None, PROJECT, developer_token=False)
    assert problem is not None
    assert "not an in-Kingdom location" in problem


def test_development_is_otherwise_not_bound() -> None:
    assert residency_problem(False, None, "https://localhost:1", "", developer_token=True) is None
