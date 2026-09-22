"""The kill-switch drill: prove a capability can be turned off, and that only it goes dark.

Runs the service in process — the same app the container serves, over the same recorded
fixtures the sets run on — with the capability's switch off, calls it through the door with a
signed envelope, and shows the backend-facing refusal, the metric that moved and a neighbour
still answering. `make drill CAP=<capability>` prints the transcript a record pastes.
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Environment, Settings
from catalyst_ai.platform.auth import capability_of
from catalyst_ai.platform.observability.metrics import ERRORS, PROVIDER_CALLS
from catalyst_ai.providers.recorded import RecordedTransport
from tools import evalkit
from tools.origin import SigningAuth

FIXTURES = Path("tests") / "fixtures" / "providers" / "gemini"
SETS = Path("evals")
NEIGHBOUR = "translate"
DISABLED = "ai.capability.disabled"
PATHS = {
    "summarize": "/v1/summarize",
    "translate": "/v1/translate",
    "improve-story": "/v1/improve-story",
    "release-notes": "/v1/release-notes",
    "post-mortem": "/v1/post-mortem",
    "generate-children": "/v1/generate-children",
    "generate-tests": "/v1/generate-tests",
    "propose-workflow": "/v1/propose-workflow",
}


def first_case(capability: str) -> dict[str, Any]:
    """Return the first case of the set — the request its fixtures were recorded for."""
    cases = evalkit.load_cases(SETS / capability / "set.jsonl")
    return dict(cases[0].input)


def settings_with(capability: str, *, enabled: bool) -> Settings:
    """Inert settings with one capability's switch in the given position."""
    field = f"capability_{capability.replace('-', '_')}"
    return evalkit.inert_settings().model_copy(
        update={field: CapabilitySettings(enabled=enabled), "environment": Environment.DEVELOPMENT}
    )


async def _call(settings: Settings, capability: str) -> tuple[int, str, float, float]:
    """Call one capability over its own recorded fixtures and read what the metrics saw."""
    runtime = evalkit.runtime_over(RecordedTransport(FIXTURES / capability), settings)
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://drill",
        auth=SigningAuth(capability_of(app), runtime.clock),
        timeout=30.0,
    ) as client:
        response = await client.post(PATHS[capability], json=first_case(capability))
    metrics = app.state.metrics
    code = str(response.json().get("error", {}).get("code", "")) if response.is_error else "served"
    return (
        response.status_code,
        code,
        metrics.value(ERRORS, {"code": DISABLED}),
        metrics.total(PROVIDER_CALLS),
    )


async def drill(capability: str) -> int:
    """Call the capability with its switch off, then on, and print what changed."""
    if capability not in PATHS:
        print(f"drill: no path for {capability}; add it to tools/drill.py")
        return 1
    disabled = settings_with(capability, enabled=False)
    off = await _call(disabled, capability)
    on = await _call(settings_with(capability, enabled=True), capability)
    neighbour = NEIGHBOUR if capability != NEIGHBOUR else "summarize"
    beside = await _call(disabled, neighbour)
    print(f"drill {capability}: switch off -> {off[0]} {off[1]}")
    print(f"  {DISABLED} counted: {off[2]:g}; provider calls: {off[3]:g}")
    print(f"drill {capability}: switch on  -> {on[0]} {on[1]}")
    print(f"  {DISABLED} counted: {on[2]:g}; provider calls: {on[3]:g}")
    print(f"drill {neighbour} while {capability} is off -> {beside[0]} {beside[1]}")
    refused = off[0] == 503 and off[1] == DISABLED and off[3] == 0
    served = on[0] == 200 and on[3] >= 1
    alone = beside[0] == 200
    works = refused and served and alone
    print("drill: the switch works" if works else "drill: the switch did not behave")
    return 0 if works else 1


def main(argv: list[str] | None = None) -> int:
    """`make drill CAP=<capability>`; the capability needs a path above and a recorded set."""
    parser = argparse.ArgumentParser(prog="drill")
    parser.add_argument("--capability", required=True)
    args = parser.parse_args(argv)
    return asyncio.run(drill(args.capability))


if __name__ == "__main__":
    sys.exit(main())
