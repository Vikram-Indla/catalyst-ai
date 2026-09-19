"""RULE-001 §1: no duplicate block of six statements across pipelines, adapters, retrieval."""

import ast
from collections import defaultdict
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

SCOPES = (rules.SRC / "capabilities", rules.SRC / "providers", rules.SRC / "retrieval")


class _Normaliser(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.AST:
        return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        return ast.copy_location(ast.Constant(value="_"), node)


def _fingerprint(statement: ast.stmt) -> str:
    return ast.dump(_Normaliser().visit(statement), annotate_fields=False)


def _windows(body: list[ast.stmt]) -> list[tuple[int, str]]:
    prints = [_fingerprint(statement) for statement in body]
    size = rules.DUPLICATE_WINDOW
    return [(body[i].lineno, "|".join(prints[i : i + size])) for i in range(len(body) - size + 1)]


def run(root: Path) -> list[Violation]:
    """Report every window of statements that appears in two places."""
    seen: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path in walk(root, *SCOPES):
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                for line, key in _windows(node.body):
                    seen[key].append((relative(path, root), line))
    violations = []
    for places in seen.values():
        if len(places) > 1:
            first, *others = places
            for where, line in others:
                message = f"duplicates {first[0]}:{first[1]} ({rules.DUPLICATE_WINDOW} statements)"
                violations.append(Violation(where, line, message))
    return violations
