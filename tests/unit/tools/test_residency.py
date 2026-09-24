"""The residency check: the tree is green; a host outside the allowlist or a lost rule is red."""

from pathlib import Path

import pytest

from tools.checks import residency

ALLOWED = frozenset({"me-central2"})


def test_the_committed_tree_keeps_tenant_text_in_the_kingdom() -> None:
    assert residency.run(Path.cwd()) == []


def test_the_allowlist_is_read_from_the_residency_module() -> None:
    source = (Path.cwd() / residency.RESIDENCY).read_text(encoding="utf-8")
    assert residency.allowed_locations(source) == ALLOWED
    assert residency.allowed_locations('IN_KINGDOM_LOCATIONS = frozenset({"a-1", "b-2"})') == {
        "a-1",
        "b-2",
    }


@pytest.mark.parametrize(
    "url",
    [
        "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent",
        "https://aiplatform.googleapis.com/v1/projects/p/locations/global",
        "https://us-central1-aiplatform.googleapis.com",
        "https://europe-west4-aiplatform.googleapis.com",
    ],
    ids=["developer api", "global", "another region", "multi-region neighbour"],
)
def test_a_host_outside_the_allowlist_is_red(url: str) -> None:
    found = residency.host_violations(f'BASE = "{url}"\n', "w", ALLOWED)
    assert [violation.line for violation in found] == [1]


def test_an_allowed_locations_endpoint_passes_and_a_new_one_passes_once_allowed() -> None:
    assert (
        residency.host_violations("https://me-central2-aiplatform.googleapis.com", "w", ALLOWED)
        == []
    )
    other = "https://me-west9-aiplatform.googleapis.com"
    assert residency.host_violations(other, "w", ALLOWED)
    assert residency.host_violations(other, "w", ALLOWED | {"me-west9"}) == []


def test_settings_that_lost_the_rule_are_red() -> None:
    texts = {
        residency.SETTINGS: "x = 1\n",
        residency.RESIDENCY: "y = 2\n",
        residency.DEPLOYED: "z = 3\n",
    }
    assert len(residency.kept_violations(texts)) == len(residency.KEPT) + 1
