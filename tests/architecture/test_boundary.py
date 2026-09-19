"""ARCH-002, ARCH-012 §4: the boundary as executable invariants; each wraps its check."""

import ast
from collections.abc import Sequence
from pathlib import Path

from tests.conftest import REPO_ROOT
from tools import rules
from tools.checks import boundary, classification, config, tenancy
from tools.checks.gate import imported_names, parse, walk

SRC = REPO_ROOT / rules.SRC


def _violation_lines(found: Sequence[object]) -> str:
    return "\n".join(str(v) for v in found)


def test_no_product_schema_import() -> None:
    found = [v for v in boundary.run(REPO_ROOT) if "product table" in v.message]
    assert not found, "ARCHITECTURE VIOLATION: a module names a product table\n" + _violation_lines(
        found
    )


def test_no_product_database_config() -> None:
    found = [v for v in boundary.run(REPO_ROOT) if "product database" in v.message]
    assert not found, (
        "ARCHITECTURE VIOLATION: the product database is configured\n" + _violation_lines(found)
    )


def test_service_never_calls_backend() -> None:
    found = [v for v in boundary.run(REPO_ROOT) if "call the backend" in v.message]
    assert not found, (
        "ARCHITECTURE VIOLATION: a way to call the backend exists\n" + _violation_lines(found)
    )


def test_every_request_field_is_classified() -> None:
    found = [v for v in classification.run(REPO_ROOT) if "no data class" in v.message]
    assert not found, "ARCHITECTURE VIOLATION: unclassified request field\n" + _violation_lines(
        found
    )


def test_no_restricted_field_in_contract() -> None:
    found = [v for v in classification.run(REPO_ROOT) if "RESTRICTED" in v.message]
    assert not found, (
        "ARCHITECTURE VIOLATION: a RESTRICTED field in the contract\n" + _violation_lines(found)
    )


def test_every_tenant_table_has_rls() -> None:
    found = [
        v
        for v in tenancy.run(REPO_ROOT)
        if "row level security" in v.message or "policy" in v.message
    ]
    assert not found, "ARCHITECTURE VIOLATION: tenant table without RLS\n" + _violation_lines(found)


def test_every_storage_query_is_tenant_scoped() -> None:
    found = [v for v in tenancy.run(REPO_ROOT) if "without organization_id" in v.message]
    assert not found, "ARCHITECTURE VIOLATION: unscoped query\n" + _violation_lines(found)


def test_config_is_the_only_environment_reader() -> None:
    found = [v for v in config.run(REPO_ROOT) if "environment" in v.message]
    assert not found, (
        "ARCHITECTURE VIOLATION: environment read outside config/\n" + _violation_lines(found)
    )


def _named_definitions(path: Path) -> list[tuple[int, str]]:
    return [
        (node.lineno, node.name)
        for node in ast.walk(parse(path))
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def test_platform_holds_no_product_noun() -> None:
    nouns = ("work_item", "workitem", "project", "sprint", "release", "incident", "epic", "story")
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{line} {name}"
        for path in walk(REPO_ROOT, rules.SRC / "platform")
        for line, name in _named_definitions(path)
        if any(noun in name.lower() for noun in nouns)
    ]
    assert not offenders, "ARCHITECTURE VIOLATION: product noun in platform/\n" + "\n".join(
        offenders
    )


def test_contract_is_a_leaf() -> None:
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{line} imports {module}"
        for path in walk(REPO_ROOT, rules.SRC / "contract")
        for line, module in imported_names(parse(path))
        if module.startswith("catalyst_ai.") and not module.startswith("catalyst_ai.contract")
    ]
    assert not offenders, "ARCHITECTURE VIOLATION: the contract imports inward\n" + "\n".join(
        offenders
    )


def _capability_packages() -> list[Path]:
    return sorted(
        p for p in (SRC / "capabilities").glob("*/") if p.is_dir() and (p / "__init__.py").exists()
    )


def _foreign_capability_imports(package: Path) -> list[str]:
    prefix = "catalyst_ai.capabilities."
    return [
        f"{path.relative_to(REPO_ROOT)}:{line} imports {module}"
        for path in walk(REPO_ROOT, package.relative_to(REPO_ROOT))
        for line, module in imported_names(parse(path))
        if module.startswith(prefix) and module.split(".")[2] != package.name
    ]


def test_capabilities_are_independent() -> None:
    offenders = [
        o for package in _capability_packages() for o in _foreign_capability_imports(package)
    ]
    assert not offenders, "ARCHITECTURE VIOLATION: capabilities import each other\n" + "\n".join(
        offenders
    )


def test_providers_only_via_port() -> None:
    found = [
        v for v in boundary.run(REPO_ROOT) if "adapter" in v.message or "imports httpx" in v.message
    ]
    assert not found, (
        "ARCHITECTURE VIOLATION: a capability reaches past the port\n" + _violation_lines(found)
    )
