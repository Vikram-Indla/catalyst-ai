"""The chain as the model reads it, and what an answer may rest on: its ids and its numbers.

The chain is rendered one fact per line, each line led by the id an answer must cite, and "not
measured" written out where the chain has no value, so zero is never implied. The same chain
gives the set of ids a sentence may cite and the set of numbers a sentence may state; a number in
the answer counts as seen when it equals one of those numerically, in either digit script.
"""

import re

from catalyst_ai.contract.brief import Chain, KeyResult, Objective, ProjectCard

NOT_MEASURED = "not measured"
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")


def _figure(value: float | None) -> str:
    if value is None:
        return NOT_MEASURED
    return f"{value:g}"


def _measure(value: float | None, unit: str | None) -> str:
    return f"{_figure(value)} {unit}" if value is not None and unit else _figure(value)


def _key_result_line(result: KeyResult) -> str:
    as_of = f" as of {result.as_of.isoformat()}" if result.as_of else ""
    value, target = _measure(result.value, result.unit), _measure(result.target, result.unit)
    return f"  key result [{result.id}] value {value}, target {target}{as_of}: {result.title}"


def _objective_lines(objective: Objective) -> list[str]:
    progress = _figure(objective.progress)
    shown = f"{progress}%" if objective.progress is not None else progress
    head = (
        f"objective [{objective.id}] status {objective.status}, progress {shown}: {objective.title}"
    )
    return [head] + [_key_result_line(result) for result in objective.key_results]


def _project_line(project: ProjectCard) -> str:
    blocked = ", blocked" if project.blocked else ""
    return (
        f"project [{project.id}] delivery health {project.delivery_health}, strategic health "
        f"{project.strategic_health}{blocked}: {project.title}"
    )


def render(chain: Chain) -> str:
    """Return the chain one fact per line, each led by the id an answer cites."""
    theme = chain.theme
    lines = [f"theme [{theme.id}]: {theme.title}"]
    if theme.charter_summary:
        lines.append(f"charter: {theme.charter_summary}")
    for objective in chain.objectives:
        lines.extend(_objective_lines(objective))
    lines.extend(_project_line(project) for project in chain.projects)
    lines.extend(
        f"finding [{finding.id}] severity {finding.severity}: {finding.text}"
        for finding in chain.findings
    )
    return "\n".join(lines)


def ids_of(chain: Chain) -> set[str]:
    """Return every id a sentence may cite."""
    ids = {chain.theme.id}
    ids |= {objective.id for objective in chain.objectives}
    ids |= {result.id for objective in chain.objectives for result in objective.key_results}
    ids |= {project.id for project in chain.projects}
    return ids | {finding.id for finding in chain.findings}


def is_empty(chain: Chain) -> bool:
    """Return whether the chain carries nothing to brief: no objective, project or finding."""
    return not (chain.objectives or chain.projects or chain.findings)


def numbers_in(text: str) -> set[float]:
    """Return every number in the text, Arabic-Indic digits read as their values."""
    found = NUMBER.findall(text.translate(ARABIC_DIGITS))
    return {float(number.replace(",", ".")) for number in found}


def unseen_numbers(answer: str, chain: Chain) -> set[float]:
    """Return the numbers the answer states that the rendered chain does not carry."""
    return numbers_in(answer) - numbers_in(render(chain))
