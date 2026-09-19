"""Render the contract document from the app: `make api` writes it, the drift check compares."""

import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import SecretStr

from catalyst_ai.app import create_app, render_openapi
from catalyst_ai.config import Environment, Settings
from tools import rules

RENDER_BEARER = "render-only"
RENDER_DATABASE = "postgresql://render:render@localhost/render"


def render() -> dict[str, Any]:
    """Build the app with inert settings and render its document."""
    settings = Settings(
        environment=Environment.DEVELOPMENT,
        service_tokens=[SecretStr(RENDER_BEARER)],
        database_url=SecretStr(RENDER_DATABASE),
    )
    return render_openapi(create_app(settings))


def dump(document: dict[str, Any]) -> str:
    """Return the canonical YAML text: sorted keys, no aliases, UTF-8."""
    return str(yaml.safe_dump(document, sort_keys=True, allow_unicode=True, width=100))


def load(path: Path) -> dict[str, Any]:
    """Read the committed document."""
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def main(argv: list[str]) -> int:
    """Write the document (`--write`) or print whether it matches the committed one."""
    target = Path(rules.API_DOCUMENT)
    document = render()
    if "--write" in argv:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dump(document), encoding="utf-8")
        print(f"wrote {target}")
        return 0
    if not target.exists() or load(target) != document:
        print(f"{target} drifts from the app; run `make api`")
        return 1
    print(f"{target} matches the app")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
