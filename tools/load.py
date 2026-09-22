"""A bounded load test on the one streaming path: N assistant turns at once, over fixtures.

No socket, no provider, no new dependency: the same app the container serves, driven through
the in-process transport with the recorded event streams the sets replay. What it proves is
what the service owns — that concurrent streams each end with one terminal frame, that the
per-organisation bound holds, that a spent tenant is refused rather than served slowly, and
what the latency looks like when N of them run together. One organisation drives them all —
the fixture is keyed by the request, so the tenant cannot vary — which is the bound worth
proving: a single tenant may not take the process. `make load` prints the numbers.
"""

import argparse
import asyncio
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx

from catalyst_ai.app import create_app
from catalyst_ai.platform.auth import capability_of
from catalyst_ai.platform.budgets import TenantBudgets
from catalyst_ai.platform.observability.metrics import ERRORS, PROVIDER_CALLS
from catalyst_ai.providers.recorded import RecordedTransport
from tools import evalkit
from tools.origin import SigningAuth

STREAM = "/v1/assistant/turn:stream"
CAPABILITY = "assistant"
FIXTURES = Path("tests") / "fixtures" / "providers" / "gemini" / CAPABILITY
SET = Path("evals") / CAPABILITY / "set.jsonl"
BUDGET_EXCEEDED = "ai.budget.exceeded"
PERCENTILE = 95
UNLIMITED_MICROS = 10**9


def _case() -> dict[str, Any]:
    return dict(evalkit.load_cases(SET)[0].input)


def _request() -> dict[str, Any]:
    """Return the set's own case: the fixture is keyed by the request, so nothing may move."""
    return _case()


async def _one(client: httpx.AsyncClient) -> tuple[float, str, int]:
    """Run one streamed turn; return its duration, its terminal frame's kind and the frame count."""
    started = time.perf_counter()
    kinds = []
    async with client.stream("POST", STREAM, json=_request()) as response:
        if response.status_code != 200:
            await response.aread()
            body = response.json().get("error", {})
            return time.perf_counter() - started, str(body.get("code", response.status_code)), 0
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                kinds.append(line.removeprefix("event: ").strip())
    return time.perf_counter() - started, kinds[-1] if kinds else "none", len(kinds)


async def _run(concurrency: int, rounds: int, *, spent: bool = False) -> dict[str, Any]:
    """Ingest the corpus, then drive the streams; `spent` leaves the tenant no budget for them."""
    settings = evalkit.inert_settings().model_copy(
        update={"tenant_budget_default_micros_per_day": UNLIMITED_MICROS}
    )
    runtime = evalkit.runtime_over(RecordedTransport(FIXTURES), settings)
    await evalkit.ingest_corpus(runtime, SET.parent)
    if spent:
        runtime = replace(
            runtime,
            budgets=TenantBudgets(runtime.clock, 1, settings.tenant_concurrency_max),
        )
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    durations: list[float] = []
    terminals: dict[str, int] = {}
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://load",
        auth=SigningAuth(capability_of(app), runtime.clock),
        timeout=60.0,
    ) as client:
        for _ in range(rounds):
            results = await asyncio.gather(*(_one(client) for _ in range(concurrency)))
            for duration, terminal, _frames in results:
                durations.append(duration)
                terminals[terminal] = terminals.get(terminal, 0) + 1
    metrics = app.state.metrics
    return {
        "streams": len(durations),
        "terminals": terminals,
        "p50_ms": statistics.median(durations) * 1000,
        "p95_ms": _percentile(durations, PERCENTILE) * 1000,
        "max_ms": max(durations) * 1000,
        "provider_calls": metrics.total(PROVIDER_CALLS),
        "budget_refusals": metrics.value(ERRORS, {"code": BUDGET_EXCEEDED}),
    }


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(percentile / 100 * len(ordered)) - 1)
    return ordered[max(0, index)]


def _print(title: str, result: dict[str, Any]) -> None:
    print(f"load {title}: {result['streams']} streams, terminals {result['terminals']}")
    print(
        f"  p50 {result['p50_ms']:.0f} ms · p95 {result['p95_ms']:.0f} ms · max "
        f"{result['max_ms']:.0f} ms · provider calls {result['provider_calls']:g} · "
        f"budget refusals {result['budget_refusals']:g}"
    )


async def load(concurrency: int, rounds: int) -> int:
    """Run the streams at the given concurrency, then once more against a spent tenant."""
    result = await _run(concurrency, rounds)
    _print(f"{concurrency}x{rounds}", result)
    refused = await _run(concurrency, 1, spent=True)
    _print("spent tenant", refused)
    every_stream_terminated = set(result["terminals"]) <= {"done", "error"}
    refused_cleanly = (
        refused["terminals"].get("error", 0) == concurrency
        and refused["budget_refusals"] == concurrency
    )
    ok = every_stream_terminated and refused_cleanly and result["terminals"].get("done", 0) > 0
    print("load: every stream terminated and a spent tenant was refused" if ok else "load: red")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    """`make load` — concurrency and rounds are flags so a bigger run is one command away."""
    parser = argparse.ArgumentParser(prog="load")
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=4)
    args = parser.parse_args(argv)
    return asyncio.run(load(args.concurrency, args.rounds))


if __name__ == "__main__":
    sys.exit(main())
