"""RULE-004 §4: no network in the suite — sockets disabled, every client carries a transport."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

CONFTEST = rules.TESTS / "conftest.py"
PYTEST_INI = Path("pytest.ini")
SOCKET_GUARD = "--disable-socket"
CLIENT_CALLS = ("httpx.AsyncClient", "httpx.Client", "AsyncClient", "Client")
NETWORK_CALLS = (
    "httpx.get",
    "httpx.post",
    "requests.get",
    "requests.post",
    "urlopen",
    "socket.create_connection",
)


def _has_transport(call: ast.Call) -> bool:
    return any(keyword.arg == "transport" for keyword in call.keywords)


def _test_violations(root: Path) -> list[Violation]:
    violations = []
    for path in walk(root, rules.TESTS):
        for node in ast.walk(parse(path)):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            if name in CLIENT_CALLS and not _has_transport(node):
                violations.append(
                    Violation(
                        relative(path, root), node.lineno, f"{name} without transport= in a test"
                    )
                )
            if name in NETWORK_CALLS:
                violations.append(Violation(relative(path, root), node.lineno, f"{name} in a test"))
    return violations


def run(root: Path) -> list[Violation]:
    """Report a suite without the socket guard and clients or calls that would reach the network."""
    violations = []
    ini = root / PYTEST_INI
    if not ini.exists() or SOCKET_GUARD not in ini.read_text(encoding="utf-8"):
        violations.append(
            Violation(PYTEST_INI.as_posix(), 1, f"the suite does not run with {SOCKET_GUARD}")
        )
    return violations + _test_violations(root)
