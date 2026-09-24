"""A grammar shaped like the one the backend sends: the list view's fields, their values, functions."""

from catalyst_ai.contract.interpret_query import Grammar, GrammarField, GrammarFunction, Operator

TEXT_OPS: list[Operator] = ["=", "!=", "in", "not in", "is", "is not", "was", "changed"]
DATE_OPS: list[Operator] = ["=", "!=", "<", ">", "<=", ">="]
ORDERED_OPS: list[Operator] = ["=", "!=", "<", ">", "<=", ">=", "in", "not in"]

GRAMMAR = Grammar(
    fields=[
        GrammarField(name="project", type="string", operators=TEXT_OPS),
        GrammarField(
            name="issuetype",
            type="string",
            operators=TEXT_OPS,
            values=["Epic", "Story", "Task", "Bug", "Sub-task"],
        ),
        GrammarField(
            name="status",
            type="string",
            operators=TEXT_OPS,
            values=["To Do", "In Progress", "In Review", "Done"],
        ),
        GrammarField(name="assignee", type="user", operators=TEXT_OPS),
        GrammarField(name="reporter", type="user", operators=TEXT_OPS),
        GrammarField(
            name="priority",
            type="string",
            operators=ORDERED_OPS,
            values=["Highest", "High", "Medium", "Low", "Lowest"],
        ),
        GrammarField(name="labels", type="array", operators=TEXT_OPS),
        GrammarField(name="sprint", type="string", operators=TEXT_OPS),
        GrammarField(name="storypoints", type="number", operators=ORDERED_OPS),
        GrammarField(name="created", type="date", operators=DATE_OPS),
        GrammarField(name="updated", type="date", operators=DATE_OPS),
        GrammarField(name="duedate", type="date", operators=DATE_OPS),
    ],
    functions=[
        GrammarFunction(name="currentUser()", type="user"),
        GrammarFunction(name="startOfWeek()", type="date"),
        GrammarFunction(name="endOfWeek()", type="date"),
        GrammarFunction(name="startOfMonth()", type="date"),
        GrammarFunction(name="openSprints()", type="string"),
    ],
)
