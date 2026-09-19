"""Token-set similarity: normalised Jaccard with containment, deterministic and language-neutral."""

import re
import unicodedata

TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "of",
        "and",
        "or",
        "for",
        "in",
        "on",
        "as",
        "is",
        "be",
        "with",
        "by",
        "at",
        "it",
    }
)
MIN_TOKEN = 2
STEM = 4


def normalise(text: str) -> frozenset[str]:
    """Lower-cased, accent-stripped, prefix-stemmed tokens without stop words."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    tokens = (t for t in TOKEN.findall(folded) if len(t) >= MIN_TOKEN and t not in STOP)
    return frozenset(t[:STEM] for t in tokens)


def similarity(left: str, right: str) -> float:
    """Max of Jaccard and containment over the token sets; 0 for an empty side."""
    a, b = normalise(left), normalise(right)
    if not a or not b:
        return 0.0
    common = len(a & b)
    jaccard = common / len(a | b)
    containment = common / min(len(a), len(b))
    return max(jaccard, containment)


def nearest(text: str, candidates: list[str], threshold: float) -> str | None:
    """Return the most similar candidate at or above the threshold, or None."""
    best: tuple[float, str] | None = None
    for candidate in candidates:
        score = similarity(text, candidate)
        if score >= threshold and (best is None or score > best[0]):
            best = (score, candidate)
    return best[1] if best else None
