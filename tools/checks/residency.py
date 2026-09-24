"""ARCH-002 §4 and ARCH-005 §6: tenant text goes to an in-Kingdom region of the provider only.

The region is configuration; the rule is the allowlist of in-Kingdom locations in
`config/residency.py`, and this check reads it from there rather than naming a region itself. Two
rules. No provider host is named anywhere the service or its tooling is configured unless it is
the regional endpoint of an allowed location — not the Developer API, not the global endpoint,
not another region — so a fallback cannot creep back in a default, a script or a dashboard. And
the settings keep the rule: the residency module builds the endpoint from the location and holds
a non-empty allowlist, and the settings validator applies it, so staging and production refuse
any other origin at load. The tests may name other hosts, to prove the refusal; they are not
walked.
"""

import ast
import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, relative, walk

PROVIDER_HOST = re.compile(r"[\w.{}-]*(?:aiplatform|generativelanguage)\.googleapis\.com")
HOST_TEMPLATE = "{location}-aiplatform.googleapis.com"
ALLOWLIST = "IN_KINGDOM_LOCATIONS"
WALKED = (rules.SRC, rules.TOOLS, Path("ops"))
WALKED_SUFFIXES = (".py", ".yaml", ".json")
ENV_EXAMPLE = Path(".env.example")
SETTINGS = rules.SRC / "config" / "settings.py"
RESIDENCY = rules.SRC / "config" / "residency.py"
DEPLOYED = rules.SRC / "config" / "deployed.py"
KEPT = (
    (SETTINGS, "start_problem(self)", "the settings do not apply the refusals"),
    (DEPLOYED, "residency_problem(", "the refusals do not include the residency rule"),
    (
        RESIDENCY,
        f'"https://{HOST_TEMPLATE}"',
        "the residency module does not build the endpoint from the location",
    ),
)
NO_ALLOWLIST = "the residency module holds no in-Kingdom location"


def allowed_locations(residency_source: str) -> frozenset[str]:
    """Return the string literals of the allowlist in the residency module's source."""
    for node in ast.walk(ast.parse(residency_source)):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == ALLOWLIST for target in node.targets
        ):
            return frozenset(
                leaf.value
                for leaf in ast.walk(node.value)
                if isinstance(leaf, ast.Constant) and isinstance(leaf.value, str)
            )
    return frozenset()


def host_violations(text: str, where: str, locations: frozenset[str]) -> list[Violation]:
    """Report every provider host that is not an allowed endpoint (or the endpoint template)."""
    allowed = {HOST_TEMPLATE.format(location=location) for location in locations}
    allowed.add(HOST_TEMPLATE)
    violations = []
    for number, line in enumerate(text.splitlines(), start=1):
        for host in PROVIDER_HOST.findall(line):
            if host not in allowed:
                violations.append(Violation(where, number, f"{host} is not an in-Kingdom endpoint"))
    return violations


def kept_violations(texts: dict[Path, str]) -> list[Violation]:
    """Report the settings or the residency module no longer holding the rule."""
    violations = [
        Violation(str(path), 1, reason)
        for path, anchor, reason in KEPT
        if anchor not in texts.get(path, "")
    ]
    if not allowed_locations(texts.get(RESIDENCY, "")):
        violations.append(Violation(str(RESIDENCY), 1, NO_ALLOWLIST))
    return violations


def run(root: Path) -> list[Violation]:
    """Report a provider host outside the allowlist, or settings that stopped enforcing it."""
    paths = (SETTINGS, RESIDENCY, DEPLOYED)
    texts = {path: (root / path).read_text(encoding="utf-8") for path in paths}
    locations = allowed_locations(texts[RESIDENCY])
    files = [path for suffix in WALKED_SUFFIXES for path in walk(root, *WALKED, suffix=suffix)]
    if (root / ENV_EXAMPLE).exists():
        files.append(root / ENV_EXAMPLE)
    violations: list[Violation] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        violations += host_violations(text, relative(path, root), locations)
    return violations + kept_violations(texts)
