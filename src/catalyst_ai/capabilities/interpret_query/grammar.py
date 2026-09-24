"""The query language, checked against the grammar the backend sent, and written back canonically.

A query is clauses (`field op value`, `field in (…)`, `field is empty`, `field was value`,
`field changed`) joined by `and`, `or`, `not` and parentheses, then an optional `order by`.
Every field must be one the grammar names, every operator one that field accepts, and every value
one of its closed set, a function of its type, or a literal of its type. `canonical` writes the
parse back with keywords in capitals, fields and closed values in the grammar's own spelling, and
the operands of `and` and `or` sorted, so two queries that mean the same compare equal.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from catalyst_ai.contract.interpret_query import Grammar, GrammarField, Operator

TOKEN = re.compile(
    r'\s*(?:(?P<string>"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')|(?P<op><=|>=|!=|=|<|>)'
    r"|(?P<punct>[(),])|(?P<word>[^\s(),=<>!\"']+(?:\(\))?))"
)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RELATIVE = re.compile(r"^-\d{1,4}[dwmy]$")
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
QUOTES = "\"'"
EMPTY_WORDS = ("empty", "null")
LIST_OPERATORS = ("in", "not in")
EMPTY_OPERATORS = ("is", "is not")
UNKNOWN = GrammarField(name="unknown", type="string", operators=["="])
LITERALS: Mapping[str, Callable[[str], bool]] = MappingProxyType(
    {
        "date": lambda text: bool(DATE.match(text) or RELATIVE.match(text)),
        "number": lambda text: bool(NUMBER.match(text)),
    }
)


class GrammarError(Exception):
    """A query that does not parse, or names what the grammar does not allow."""

    def __init__(self, problems: list[str]) -> None:
        """Hold every problem found, as `code: term`."""
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Clause:
    """One condition on one field; `values` is empty for `changed`, `("EMPTY",)` for `is`."""

    name: str
    operator: str
    values: tuple[str, ...]

    def written(self) -> str:
        """Write the clause canonically."""
        if self.operator == "CHANGED":
            return f"{self.name} CHANGED"
        if self.values == ("EMPTY",):
            return f"{self.name} {self.operator} EMPTY"
        quoted = [value if value.endswith("()") else f'"{value}"' for value in self.values]
        shown = f"({', '.join(quoted)})" if self.operator in ("IN", "NOT IN") else quoted[0]
        return f"{self.name} {self.operator} {shown}"


@dataclass(frozen=True)
class Negation:
    """`not` over one part of the query."""

    child: "Node"

    def written(self) -> str:
        """Write the negation canonically."""
        return f"NOT ({self.child.written()})"


@dataclass(frozen=True)
class Junction:
    """`and` or `or` over two or more parts; their order does not change the meaning."""

    kind: str
    children: tuple["Node", ...]

    def written(self) -> str:
        """Write the parts sorted, each in parentheses when it is itself a junction."""
        parts = sorted(
            f"({child.written()})" if isinstance(child, Junction) else child.written()
            for child in self.children
        )
        return f" {self.kind} ".join(parts)


Node = Clause | Negation | Junction
PartReader = Callable[[], Node]


@dataclass
class Parser:
    """A recursive-descent reading of one query against one grammar."""

    tokens: list[str]
    grammar: Grammar
    position: int = 0
    problems: list[str] = field(default_factory=list)

    def peek(self) -> str:
        """Return the next token, lower-cased, or '' at the end."""
        return self.tokens[self.position].lower() if self.position < len(self.tokens) else ""

    def take(self) -> str:
        """Consume and return the next token as written."""
        token = self.tokens[self.position] if self.position < len(self.tokens) else ""
        self.position += 1
        return token

    def expect(self, word: str) -> None:
        """Consume the word, or record that it was missing."""
        if self.take().lower() != word:
            self.problems.append(f"syntax: expected {word}")

    def junction(self, kind: str, part: PartReader) -> Node:
        """Read parts joined by `kind`; one part stands alone."""
        parts = [part()]
        while self.peek() == kind.lower():
            self.take()
            parts.append(part())
        return parts[0] if len(parts) == 1 else Junction(kind, tuple(parts))

    def expression(self) -> Node:
        """Read `or` over `and` over factors."""
        return self.junction("OR", lambda: self.junction("AND", self.factor))

    def factor(self) -> Node:
        """Read a negation, a parenthesised expression or a clause."""
        if self.peek() == "not":
            self.take()
            return Negation(self.factor())
        if self.peek() == "(":
            self.take()
            inner = self.expression()
            self.expect(")")
            return inner
        return self.clause()

    def clause(self) -> Clause:
        """Read one clause and hold its field, operator and values to the grammar."""
        name = self.take()
        spec = field_of(self.grammar, name)
        if spec is None:
            self.problems.append(f"unknown_field: {name}")
        spec = spec or UNKNOWN
        operator = self.operator()
        base = "was" if operator == "was not" else operator
        if spec is not UNKNOWN and base not in allowed_operators(spec):
            self.problems.append(f"operator_not_allowed: {spec.name} {operator}")
        return Clause(spec.name, operator.upper(), self.operand(spec, operator))

    def operator(self) -> str:
        """Read an operator, joining the two-word ones."""
        first = self.take().lower()
        second = self.peek()
        if (first, second) in (("not", "in"), ("is", "not"), ("was", "not")):
            self.take()
            return "not in" if first == "not" else f"{first} not"
        return first

    def operand(self, spec: GrammarField, operator: str) -> tuple[str, ...]:
        """Read what the operator takes: nothing, `empty`, a list, or one value."""
        if operator == "changed":
            return ()
        readers = {
            **dict.fromkeys(EMPTY_OPERATORS, self.empty_word),
            **dict.fromkeys(LIST_OPERATORS, self.value_list),
        }
        reader = readers.get(operator)
        return reader(spec) if reader else (self.value(spec),)

    def empty_word(self, spec: GrammarField) -> tuple[str, ...]:
        """Read the `empty` (or `null`) that `is` and `is not` take."""
        word = self.take().lower()
        if word not in EMPTY_WORDS:
            self.problems.append(f"value_not_allowed: {spec.name} is {word}")
        return ("EMPTY",)

    def value_list(self, spec: GrammarField) -> tuple[str, ...]:
        """Read a parenthesised list of values, sorted."""
        self.expect("(")
        values = [self.value(spec)]
        while self.peek() == ",":
            self.take()
            values.append(self.value(spec))
        self.expect(")")
        return tuple(sorted(values))

    def value(self, spec: GrammarField) -> str:
        """Read one value and return it in the grammar's spelling."""
        raw = self.take()
        text = raw[1:-1] if raw[:1] in QUOTES and raw[-1:] == raw[:1] and len(raw) > 1 else raw
        resolved = value_of(self.grammar, spec, text)
        if resolved is None and spec is not UNKNOWN:
            self.problems.append(f"value_not_allowed: {spec.name} {text}")
        return resolved or text

    def ordering(self) -> list[str]:
        """Read `order by field [asc|desc], …`, holding every field to the grammar."""
        if self.peek() != "order":
            return []
        self.take()
        self.expect("by")
        order = [self.sort_key()]
        while self.peek() == ",":
            self.take()
            order.append(self.sort_key())
        return order

    def sort_key(self) -> str:
        """Read one sort field and its direction."""
        name = self.take()
        spec = field_of(self.grammar, name)
        if spec is None:
            self.problems.append(f"unknown_field: {name}")
        direction = self.take().upper() if self.peek() in ("asc", "desc") else "ASC"
        return f"{spec.name if spec else name} {direction}"


def allowed_operators(spec: GrammarField) -> set[str]:
    """Return the operators the field accepts, as plain words."""
    operators: list[Operator] = spec.operators
    return {str(operator) for operator in operators}


def field_of(grammar: Grammar, name: str) -> GrammarField | None:
    """Return the grammar's field of that name, whatever its case."""
    return next((f for f in grammar.fields if f.name.lower() == name.lower()), None)


def value_of(grammar: Grammar, spec: GrammarField, text: str) -> str | None:
    """Return the value in its canonical spelling, or None when the field does not allow it."""
    function = next(
        (
            f.name
            for f in grammar.functions
            if f.name.lower() == text.lower() and f.type == spec.type
        ),
        None,
    )
    if function is not None or text.endswith("()"):
        return function
    if spec.values is not None:
        return next((v for v in spec.values if v.lower() == text.lower()), None)
    return text if LITERALS.get(spec.type, bool)(text) else None


def tokens_of(query: str) -> list[str]:
    """Split a query into tokens; a stray character is a syntax problem, not a crash."""
    found: list[str] = []
    position, end = 0, len(query.rstrip())
    while position < end:
        match = TOKEN.match(query, position)
        if match is None or match.end() == position:
            raise GrammarError([f"syntax: unexpected {query[position : position + 10]!r}"])
        found.append(match.group(match.lastgroup or "word"))
        position = match.end()
    return found


def parse(query: str, grammar: Grammar) -> tuple[Node | None, list[str]]:
    """Parse the query against the grammar; raise `GrammarError` listing every problem."""
    parser = Parser(tokens_of(query), grammar)
    tree = None if parser.peek() in ("", "order") else parser.expression()
    order = parser.ordering()
    if parser.position < len(parser.tokens):
        parser.problems.append(f"syntax: unexpected {parser.tokens[parser.position]}")
    if tree is None and not order:
        parser.problems.append("syntax: empty query")
    if parser.problems:
        raise GrammarError(parser.problems)
    return tree, order


def canonical(query: str, grammar: Grammar) -> str:
    """Return the query written back canonically; raise `GrammarError` when it does not parse."""
    tree, order = parse(query, grammar)
    parts = [tree.written()] if tree is not None else []
    if order:
        parts.append(f"ORDER BY {', '.join(order)}")
    return " ".join(parts)
