"""The comment modes' markup rule: a polish keeps markup, a reply names no one new."""

from catalyst_ai.capabilities.improve_story.comments import (
    DROPPED,
    INVENTED,
    markup,
    markup_problem,
)
from catalyst_ai.contract.improve_story import CommentInput, ImproveStoryMode

COMMENT = CommentInput(
    participant="p2", text="see https://example.test/a and `flag_x`, @p3 please check"
)
CONTEXT = "Export board\nSee https://example.test/spec"


def test_markup_is_mentions_links_and_code_spans() -> None:
    assert markup(COMMENT.text) == {"https://example.test/a", "`flag_x`", "@p3"}


def test_a_polish_that_keeps_every_piece_passes_and_one_that_drops_any_is_refused() -> None:
    kept = "See https://example.test/a and `flag_x`; @p3, please check."
    assert markup_problem(ImproveStoryMode.POLISH_COMMENT, COMMENT, CONTEXT, kept) is None
    for dropped in (kept.replace("@p3", "them"), kept.replace("`flag_x`", "flag_x")):
        assert markup_problem(ImproveStoryMode.POLISH_COMMENT, COMMENT, CONTEXT, dropped) == DROPPED


def test_a_reply_may_name_the_author_the_mentioned_and_the_known_links_only() -> None:
    fine = "Thanks @p2, @p3 will look; the spec is https://example.test/spec"
    assert markup_problem(ImproveStoryMode.REPLY, COMMENT, CONTEXT, fine) is None
    for invented in ("Thanks @p2, @p9 will look", "Thanks @p2, see https://elsewhere.test"):
        assert markup_problem(ImproveStoryMode.REPLY, COMMENT, CONTEXT, invented) == INVENTED
