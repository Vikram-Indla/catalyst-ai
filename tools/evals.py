"""`make evals`: every set against recorded fixtures; scores, p95s, a run file; red on a floor."""

import asyncio
import json
import sys
import time
from pathlib import Path

from catalyst_ai.contract.envelopes import ResponseEnvelope
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.providers.recorded import MissingFixtureError, RecordedTransport
from tools import evalkit, rules
from tools.checks.evals import thresholds

RUNS = Path(".evals")
P95 = 0.95
MS = 1000.0


async def _run_case(
    case: evalkit.Case, runtime: RuntimeContext, name: str
) -> tuple[ResponseEnvelope, float]:
    spec = evalkit.REGISTRY[name]
    request = spec.request.model_validate(case.input)
    started = time.perf_counter()
    response = await spec.pipeline(request, runtime, f"eval-{case.id}")
    return response, (time.perf_counter() - started) * MS


async def run_set(directory: Path) -> dict[str, object]:
    """Run one set over its storage; the setup indexes what the cases search."""
    spec = evalkit.REGISTRY[directory.name]
    async with evalkit.database(spec) as storage:
        runtime = evalkit.runtime_over(
            RecordedTransport(evalkit.FIXTURES_ROOT / directory.name), storage=storage
        )
        if spec.setup is not None:
            await spec.setup(runtime, directory)
        return await _grade_set(directory, runtime)


async def _grade_set(directory: Path, runtime: RuntimeContext) -> dict[str, object]:
    name = directory.name
    cases = evalkit.load_cases(directory / "set.jsonl")
    graders = evalkit.load_graders(directory).GRADERS
    per_grader: dict[str, list[float]] = {g: [] for g in graders}
    latencies: list[float] = []
    costs: list[float] = []
    failures: list[str] = []
    for case in cases:
        try:
            response, elapsed = await _run_case(case, runtime, name)
        except (Error, MissingFixtureError) as error:
            failures.append(
                f"{case.id}: raised {type(error).__name__} {getattr(error, 'code', '')}"
            )
            for grader_name in graders:
                per_grader[grader_name].append(0.0)
            continue
        latencies.append(elapsed)
        costs.append(float(response.usage.cost_micros))
        request = evalkit.REGISTRY[name].request.model_validate(case.input)
        for grader_name, grader in graders.items():
            score = grader(request, response, case.expected)
            per_grader[grader_name].append(score)
            if score < 1.0:
                failures.append(f"{case.id}: {grader_name}={score:.2f}")
    scores = {g: sum(v) / len(v) for g, v in per_grader.items() if v}
    overall = sum(scores.values()) / len(scores) if scores else 0.0
    return {
        "set": name,
        "cases": len(cases),
        "scores": scores,
        "overall": overall,
        "p95_latency_ms": evalkit.percentile(latencies, P95),
        "p95_cost_micros": evalkit.percentile(costs, P95),
        "failures": failures,
    }


def judge(result: dict[str, object], floors: dict[str, float]) -> list[str]:
    """Return the floors the result falls under."""
    reds = []
    scores = result["scores"]
    if not isinstance(scores, dict):
        return ["no scores"]
    for key, floor in floors.items():
        if key in scores and float(scores[key]) < floor:
            reds.append(f"{key} {float(scores[key]):.3f} < {floor}")
    if float(str(result["overall"])) < floors.get("overall", 0.0):
        reds.append(f"overall {float(str(result['overall'])):.3f} < {floors['overall']}")
    for key in ("p95_latency_ms", "p95_cost_micros"):
        if key in floors and float(str(result[key])) > floors[key]:
            reds.append(f"{key} {float(str(result[key])):.0f} > {floors[key]}")
    return reds


def main(argv: list[str]) -> int:
    """Run every set (or the one named after `--set`) and write `.evals/<name>.json`."""
    only = argv[argv.index("--set") + 1] if "--set" in argv else None
    RUNS.mkdir(exist_ok=True)
    status = 0
    for directory in sorted(p for p in Path(rules.EVALS).iterdir() if p.is_dir()):
        if only and directory.name != only:
            continue
        result = asyncio.run(run_set(directory))
        floors = thresholds((directory / "thresholds.yaml").read_text(encoding="utf-8"))
        reds = judge(result, floors)
        (RUNS / f"{directory.name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        scores = result["scores"] if isinstance(result["scores"], dict) else {}
        print(f"-- {directory.name} v{_set_version(directory)} - {result['cases']} cases")
        for grader, score in scores.items():
            print(f"   {grader:<22} {float(score):.3f}  (floor {floors.get(grader, 0.0)})")
        overall = float(str(result["overall"]))
        latency = float(str(result["p95_latency_ms"]))
        cost = float(str(result["p95_cost_micros"]))
        print(f"   {'overall':<22} {overall:.3f}  (floor {floors.get('overall', 0.0)})")
        print(f"   p95 latency {latency:.0f} ms (budget {floors.get('p95_latency_ms')})")
        print(f"   p95 cost {cost:.0f} micro-dollars (budget {floors.get('p95_cost_micros')})")
        for failure in result["failures"] if isinstance(result["failures"], list) else []:
            print(f"   miss  {failure}")
        if reds:
            status = 1
            print(f"EVALS RED for {directory.name}: " + "; ".join(reds))
    print("EVALS GREEN" if status == 0 else "EVALS RED")
    return status


def _set_version(directory: Path) -> str:
    readme = (directory / "README.md").read_text(encoding="utf-8")
    for line in readme.splitlines():
        if "Set version:" in line:
            return line.split("Set version:")[1].split("·")[0].strip(" *")
    return "?"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
