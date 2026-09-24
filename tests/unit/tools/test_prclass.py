"""The class check: a branch is judged by its highest record claim against its derived radius."""

from tools.checks import prclass

PLATFORM_FILE = "src/catalyst_ai/providers/gemini/adapter.py"
SYSTEM_FILE = "src/catalyst_ai/providers/port.py"


def _record(radius: str) -> str:
    return f"# a record\n\n```\nBlast radius:    {radius} — why\n```\n"


def test_the_radius_is_derived_from_the_widest_path() -> None:
    assert prclass.derive(["brain/x.md"]) == "LOCAL"
    assert prclass.derive(["src/catalyst_ai/capabilities/brief/facts.py"]) == "CAPABILITY"
    assert prclass.derive([PLATFORM_FILE, "evals/brief/set.jsonl"]) == "PLATFORM"
    assert prclass.derive([PLATFORM_FILE, SYSTEM_FILE]) == "SYSTEM"


def test_one_record_is_judged_as_before() -> None:
    assert prclass.check([PLATFORM_FILE], {"a.md": _record("PLATFORM")}) == []
    found = prclass.check([PLATFORM_FILE], {"a.md": _record("CAPABILITY")})
    assert [v.message for v in found] == [
        "the highest claim is CAPABILITY but the changed paths derive PLATFORM"
    ]


def test_several_records_pass_when_the_highest_claim_covers_the_branch() -> None:
    records = {"a.md": _record("LOCAL"), "b.md": _record("CAPABILITY"), "c.md": _record("PLATFORM")}
    assert prclass.check([PLATFORM_FILE], records) == []


def test_several_records_all_below_the_branch_are_all_named() -> None:
    records = {"b.md": _record("CAPABILITY"), "a.md": _record("LOCAL")}
    found = prclass.check([SYSTEM_FILE], records)
    assert [v.path for v in found] == ["a.md", "b.md"]


def test_a_changed_record_that_claims_nothing_is_red_even_beside_a_covering_claim() -> None:
    records = {"a.md": "no claim here", "b.md": _record("SYSTEM")}
    found = prclass.check([SYSTEM_FILE], records)
    assert [(v.path, v.message) for v in found] == [
        ("a.md", "a changed record claims no blast radius")
    ]
