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
from tools.affected import affected_sets
from tools.checks.evals import thresholds
from tools.checks.gitinfo import changed_since_main
from tools.scope import staged

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


def _expected_refusal(case: evalkit.Case, error: Exception) -> bool:
    """Whether the case asked for exactly this refusal: the code and, when named, the detail."""
    wanted = case.expected.get("refused")
    if not isinstance(wanted, dict) or not isinstance(error, Error):
        return False
    details = {detail.code for detail in error.details}
    code_ok = error.code.value == wanted.get("code")
    detail = wanted.get("detail")
    return code_ok and (detail is None or detail in details)


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
            expected = _expected_refusal(case, error)
            if not expected:
                failures.append(
                    f"{case.id}: raised {type(error).__name__} {getattr(error, 'code', '')}"
                )
            for grader_name in graders:
                per_grader[grader_name].append(1.0 if expected else 0.0)
            continue
        if case.expected.get("refused"):
            failures.append(f"{case.id}: answered where a refusal was expected")
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


def judge(
    result: dict[str, object], floors: dict[str, float], *, budgets: bool = True
) -> list[str]:
    """Return the floors the result falls under; the latency and cost budgets only when asked."""
    reds = []
    scores = result["scores"]
    if not isinstance(scores, dict):
        return ["no scores"]
    for key, floor in floors.items():
        if key in scores and float(scores[key]) < floor:
            reds.append(f"{key} {float(scores[key]):.3f} < {floor}")
    if float(str(result["overall"])) < floors.get("overall", 0.0):
        reds.append(f"overall {float(str(result['overall'])):.3f} < {floors['overall']}")
    for key in BUDGETS if budgets else ():
        if key in floors and float(str(result[key])) > floors[key]:
            reds.append(f"{key} {float(str(result[key])):.0f} > {floors[key]}")
    return reds


BUDGETS = ("p95_latency_ms", "p95_cost_micros")
BUDGETS_ELSEWHERE = "reported only; the full gate, the hosted run and the nightly enforce it"


def selected(argv: list[str]) -> list[Path]:
    """Every set, the one named after `--set`, or with `--affected` the sets a change touches."""
    directories = sorted(p for p in Path(rules.EVALS).iterdir() if p.is_dir())
    if "--set" in argv:
        only = argv[argv.index("--set") + 1]
        return [d for d in directories if d.name == only]
    if "--affected" in argv or "--staged" in argv:
        root = Path.cwd()
        changed = staged(root) if "--staged" in argv else changed_since_main(root)
        names = affected_sets(changed, [d.name for d in directories], root)
        return [d for d in directories if d.name in names]
    return directories


def main(argv: list[str]) -> int:
    """Run the selected sets and write `.evals/<name>.json`; `--affected` is iteration only.

    `--affected` runs at commit time on a shared workstation, where a timing budget measures the
    machine's load, not the change: it judges every grader floor but only reports the latency and
    cost budgets, which the full gate enforces on a machine running nothing else.
    """
    RUNS.mkdir(exist_ok=True)
    status = 0
    budgets = "--affected" not in argv and "--staged" not in argv
    directories = selected(argv)
    if not budgets:
        print(
            f"evals: affected sets {[d.name for d in directories]} (iteration only, not evidence)"
        )
    for directory in directories:
        result = asyncio.run(run_set(directory))
        floors = thresholds((directory / "thresholds.yaml").read_text(encoding="utf-8"))
        reds = judge(result, floors, budgets=budgets)
        (RUNS / f"{directory.name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        scores = result["scores"] if isinstance(result["scores"], dict) else {}
        print(f"-- {directory.name} v{_set_version(directory)} - {result['cases']} cases")
        for grader, score in scores.items():
            print(f"   {grader:<22} {float(score):.3f}  (floor {floors.get(grader, 0.0)})")
        overall = float(str(result["overall"]))
        latency = float(str(result["p95_latency_ms"]))
        cost = float(str(result["p95_cost_micros"]))
        print(f"   {'overall':<22} {overall:.3f}  (floor {floors.get('overall', 0.0)})")
        where = "" if budgets else f"; {BUDGETS_ELSEWHERE}"
        print(f"   p95 latency {latency:.0f} ms (budget {floors.get('p95_latency_ms')}{where})")
        print(
            f"   p95 cost {cost:.0f} micro-dollars (budget {floors.get('p95_cost_micros')}{where})"
        )
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
