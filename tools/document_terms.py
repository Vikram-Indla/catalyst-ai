"""The synthetic knowledge base of the documents sets: pages per space, facts, questions.

A `Page` is (document id, title, sections as (heading, lines), facts as (question, answer
keyword, heading)).
"""

ORG = "11111111-1111-7111-8111-111111111111"
VERSION = "1.0.0"
SPACE = "kb-main"
OTHER_SPACE = "kb-other"

Page = tuple[str, str, list[tuple[str, list[str]]], list[tuple[str, str, str]]]

PAGES_HEAD: tuple[Page, ...] = (
    (
        "doc-runbook",
        "Incident runbook",
        [
            (
                "Paging",
                [
                    "Alerts page the on-call engineer through the paging service.",
                    "The on-call rota changes every Sunday at 09:00.",
                ],
            ),
            (
                "Escalation",
                [
                    "After fifteen minutes without acknowledgement the lead is paged.",
                    "After thirty minutes a bridge call is opened and the status page is updated.",
                ],
            ),
            (
                "Rollback",
                [
                    "A rollback needs the release manager's approval in the release hub.",
                    "The rollback command lives in the deploy repository under scripts.",
                ],
            ),
        ],
        [
            ("When does the on-call rota change?", "Sunday", "Paging"),
            ("What happens after fifteen minutes without acknowledgement?", "lead", "Escalation"),
            ("When is a bridge call opened?", "thirty", "Escalation"),
            ("Who approves a rollback?", "release manager", "Rollback"),
            ("Where does the rollback command live?", "deploy repository", "Rollback"),
        ],
    ),
    (
        "doc-onboarding",
        "Onboarding guide",
        [
            (
                "First day",
                [
                    "New members receive a laptop on the first day.",
                    "Accounts are created by the platform team within two business days.",
                ],
            ),
            (
                "First week",
                [
                    "Every new member pairs with a buddy for the first week.",
                    "The buddy books the introduction meetings with each hub owner.",
                ],
            ),
            (
                "Access",
                [
                    "Access to production is granted only after the security briefing.",
                    "The security briefing runs every second Tuesday.",
                ],
            ),
        ],
        [
            ("What does a new member receive on the first day?", "laptop", "First day"),
            ("How long does account creation take?", "two business days", "First day"),
            ("Who books the introduction meetings?", "buddy", "First week"),
            ("When is access to production granted?", "security briefing", "Access"),
            ("How often does the security briefing run?", "second Tuesday", "Access"),
        ],
    ),
    (
        "doc-release",
        "Release process",
        [
            (
                "Cadence",
                [
                    "Releases ship every two weeks on a Wednesday.",
                    "A release freeze starts on the Monday before the release.",
                ],
            ),
            (
                "Sign-off",
                [
                    "Each release needs sign-off from the test lead and the release manager.",
                    "Sign-off is recorded in the release hub before the freeze ends.",
                ],
            ),
            (
                "Hotfixes",
                [
                    "A hotfix skips the freeze but still needs the test lead's sign-off.",
                    "Hotfixes are tagged with the suffix hotfix in the version.",
                ],
            ),
        ],
        [
            ("How often do releases ship?", "two weeks", "Cadence"),
            ("When does the release freeze start?", "Monday", "Cadence"),
            ("Who signs off a release?", "test lead", "Sign-off"),
            ("Does a hotfix need sign-off?", "test lead", "Hotfixes"),
            ("How are hotfixes tagged?", "hotfix", "Hotfixes"),
        ],
    ),
    (
        "doc-export",
        "Board export",
        [
            (
                "Columns",
                [
                    "The export writes every visible column of the board to a CSV file.",
                    "Hidden columns are never exported.",
                ],
            ),
            (
                "Limits",
                [
                    "An export covers at most five thousand rows.",
                    "Larger boards are exported in pages named by their page number.",
                ],
            ),
            (
                "Permissions",
                [
                    "Only members with the export permission see the export button.",
                    "The permission is granted per project by the project admin.",
                ],
            ),
        ],
        [
            ("Which columns does the export write?", "visible", "Columns"),
            ("How many rows can one export cover?", "five thousand", "Limits"),
            ("Who sees the export button?", "export permission", "Permissions"),
            ("Who grants the export permission?", "project admin", "Permissions"),
        ],
    ),
    (
        "doc-billing",
        "Billing gateway",
        [
            (
                "Cut-over",
                [
                    "Billing moves to the new gateway on the first of November.",
                    "The old gateway stays in read-only mode for ninety days.",
                ],
            ),
            (
                "Retries",
                [
                    "A failed charge is retried three times, one hour apart.",
                    "After the third failure the invoice is marked as unpaid.",
                ],
            ),
        ],
        [
            ("When does billing move to the new gateway?", "November", "Cut-over"),
            ("How long does the old gateway stay read-only?", "ninety days", "Cut-over"),
            ("How many times is a failed charge retried?", "three", "Retries"),
            ("What happens after the third failure?", "unpaid", "Retries"),
        ],
    ),
)
