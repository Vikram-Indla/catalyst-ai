"""The local run: no secret value in `.env.example`, every published port on loopback, as agreed.

`.env.example` is copied to `.env` by hand, so a value it carries for a secret-shaped key
(`*_PASSWORD`, `*_KEY`, `*_KEYS`, `*_TOKEN`, `*_SECRET`) — commented out or not — would travel into
every copy. A plain word is not a pattern the leak scanner knows, so this check refuses any value
there, except the keys named in `PUBLIC_BY_DESIGN`, each with its reason. And every port
`docker-compose.yml` publishes binds `127.0.0.1` (every seeded account shares one test password),
on the ports the local-up script calls: the database 5434, the API 8090, the ops ports 9091 (api)
and 9092 (worker).
"""

import re
from pathlib import Path
from types import MappingProxyType

from tools.checks.gate import Violation

ENV_EXAMPLE = Path(".env.example")
COMPOSE = Path("docker-compose.yml")
SECRET_SHAPED = re.compile(
    r"^(?:#\s*)?(?P<key>[A-Z][A-Z0-9_]*_(?:PASSWORD|KEYS?|TOKEN|SECRET))=(?P<value>.*)$"
)
PUBLIC_BY_DESIGN = MappingProxyType(
    {
        "CATALYST_AI_AUTH_PUBLIC_KEYS": "a public verification key; the test pair's seed is public",
    }
)
PORT_LINE = re.compile(r'^\s*-\s*"(?P<mapping>[^"]+)"\s*$')
LOOPBACK = "127.0.0.1"
HOST_PORTS = frozenset({"5434", "8090", "9091", "9092"})


def env_violations(text: str, where: str) -> list[Violation]:
    """Report every secret-shaped key of the example that carries a value."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        match = SECRET_SHAPED.match(line.strip())
        if match and match.group("value").strip() and match.group("key") not in PUBLIC_BY_DESIGN:
            message = f"{match.group('key')} carries a value in the example; leave it empty"
            found.append(Violation(where, number, message))
    return found


def port_violations(text: str, where: str) -> list[Violation]:
    """Report a published port not bound to loopback, or a host port outside the agreed set."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        match = PORT_LINE.match(line)
        if not match:
            continue
        parts = match.group("mapping").split(":")
        if len(parts) != 3 or parts[0] != LOOPBACK:
            found.append(
                Violation(where, number, f"{match.group('mapping')} is not bound to {LOOPBACK}")
            )
        elif parts[1] not in HOST_PORTS:
            found.append(
                Violation(where, number, f"host port {parts[1]} is not one the local run uses")
            )
    return found


def run(root: Path) -> list[Violation]:
    """Read the example and the compose file where they exist."""
    found: list[Violation] = []
    if (root / ENV_EXAMPLE).is_file():
        found += env_violations((root / ENV_EXAMPLE).read_text(encoding="utf-8"), str(ENV_EXAMPLE))
    if (root / COMPOSE).is_file():
        found += port_violations((root / COMPOSE).read_text(encoding="utf-8"), str(COMPOSE))
    return found
