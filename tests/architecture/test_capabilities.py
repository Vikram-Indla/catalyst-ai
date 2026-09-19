"""ARCH-003, ARCH-005, ARCH-012 §4: capability, prompt, model and interface invariants."""

from tests.conftest import REPO_ROOT
from tools import api, rules
from tools.checks import (
    capabilities,
    errors,
    interfaces,
    models,
    naming,
    openapi,
    pipeline,
    prompts,
)
from tools.checks.gate import Violation


def _lines(found: list[Violation]) -> str:
    return "\n".join(v.render() for v in found)


def test_every_capability_has_descriptor() -> None:
    packages = [
        p
        for p in (REPO_ROOT / rules.SRC / "capabilities").glob("*/")
        if p.is_dir() and p.name not in rules.SKIP_DIRS
    ]
    missing = [p.name for p in packages if not (p / "descriptor.py").exists()]
    assert not missing, "ARCHITECTURE VIOLATION: capability without descriptor: " + ", ".join(
        missing
    )


def test_every_capability_has_eval_set() -> None:
    found = [v for v in capabilities.run(REPO_ROOT) if "no evals/" in v.message]
    assert not found, "ARCHITECTURE VIOLATION: capability without eval set\n" + _lines(found)


def test_every_capability_declares_budget() -> None:
    found = [
        v for v in capabilities.run(REPO_ROOT) if "p95_" in v.message or "timeout" in v.message
    ]
    assert not found, "ARCHITECTURE VIOLATION: capability without budget\n" + _lines(found)


def test_every_capability_has_kill_switch() -> None:
    found = [
        v
        for v in capabilities.run(REPO_ROOT)
        if "kill_switch" in v.message or "settings row" in v.message
    ]
    assert not found, "ARCHITECTURE VIOLATION: capability without kill switch\n" + _lines(found)


def test_every_operation_lists_error_codes() -> None:
    found = [
        v for v in openapi.operation_violations(api.render(), "api") if "x-error-codes" in v.message
    ]
    assert not found, "ARCHITECTURE VIOLATION: operation without error codes\n" + _lines(found)


def test_every_error_code_is_catalogued() -> None:
    found = errors.run(REPO_ROOT)
    assert not found, "ARCHITECTURE VIOLATION: error catalog drift\n" + _lines(found)


def test_no_model_id_outside_register() -> None:
    found = models.run(REPO_ROOT)
    assert not found, "ARCHITECTURE VIOLATION: model id outside the register\n" + _lines(found)


def test_no_prompt_string_in_code() -> None:
    found = [v for v in prompts.run(REPO_ROOT) if "in code" in v.message or "f-string" in v.message]
    assert not found, "ARCHITECTURE VIOLATION: prompt in code\n" + _lines(found)


def test_every_prompt_file_has_header() -> None:
    found = [v for v in prompts.run(REPO_ROOT) if "header" in v.message]
    assert not found, "ARCHITECTURE VIOLATION: prompt without header\n" + _lines(found)


def test_pipeline_stages_in_order() -> None:
    found = pipeline.run(REPO_ROOT)
    assert not found, "ARCHITECTURE VIOLATION: pipeline shape\n" + _lines(found)


def test_no_interface_without_substitution() -> None:
    found = interfaces.run(REPO_ROOT)
    assert not found, "ARCHITECTURE VIOLATION: interface without substitution\n" + _lines(found)


def test_no_banned_names() -> None:
    found = naming.run(REPO_ROOT)
    assert not found, "ARCHITECTURE VIOLATION: banned name\n" + _lines(found)
