"""Every alert points at a runbook that exists and is about it, by a heading that names it."""

from pathlib import Path

from tools.checks import alerts


def _document(alert: str, runbook: str) -> dict[str, object]:
    rule = {"alert": alert, "annotations": {"runbook": f"docs/06-runbooks/{runbook}"}}
    return {"groups": [{"rules": [rule, dict(rule)]}]}


def test_the_committed_alerts_runbooks_and_ledger_agree() -> None:
    assert alerts.run(Path()) == []


def test_a_runbook_whose_headings_name_the_alert_is_about_it() -> None:
    headings = alerts.headings_of("# `IndexUnavailable` — the index\n\nbody naming nothing\n")
    assert alerts.about_violations(_document("IndexUnavailable", "i.md"), {"i.md": headings}) == []


def test_an_alert_pointing_at_a_page_about_something_else_is_refused_once() -> None:
    headings = alerts.headings_of("# Index rebuild\n\nIndexUnavailable is mentioned in the body\n")
    found = alerts.about_violations(_document("IndexUnavailable", "r.md"), {"r.md": headings})
    assert [(v.path, v.message) for v in found] == [
        ("docs/06-runbooks/r.md", "IndexUnavailable points here; no heading names it")
    ]


def test_a_missing_runbook_is_the_existence_rule_not_this_one() -> None:
    document = _document("Anything", "nope.md")
    assert alerts.about_violations(document, {}) == []
    assert alerts.alert_violations(document, set(), "w") != []
