"""The register's Gemini rows: alias → concrete id, prices, context and the retention setting.

A row may name a thinking level. The 3.x models think by default and bill the thinking as
output, so a row that leaves it unset would spend tokens nobody asked for and could fill the
output allowance before the answer is written.

Prices are the published list prices (https://ai.google.dev/gemini-api/docs/pricing), read
twice on 2026-09-23. The flash row's price doubles on 2027-01-01 (1 500 / 7 500 µ$ per 1k);
the providers ledger carries the date. They are re-read for the regional provider with its model
list.

Every row is served by the regional provider in the configured in-Kingdom location
(`config/residency.py`), and every
row is **unverified in-region** until the model list of the real account shows the region serves
it there rather than routing it elsewhere. A row that turns out not to be regional changes, and
every capability on it re-runs its eval; that is a model decision, never a silent swap.
"""

from dataclasses import dataclass
from types import MappingProxyType

from catalyst_ai.providers.port import ModelAlias

PROVIDER = "gemini"
RETENTION = (
    "Vertex AI in the in-Kingdom region under the project's data terms; the account's retention "
    "settings are verified with its model list, and until then only authored inputs reach any "
    "credential"
)
UNVERIFIED_IN_REGION = "unverified in-region"


@dataclass(frozen=True)
class ModelSpec:
    """One concrete model and what it costs; prices in micro-dollars per 1 000 tokens."""

    model_id: str
    input_micros_per_1k: int
    output_micros_per_1k: int
    context_tokens: int
    thinking_level: str | None = None
    residency: str = UNVERIFIED_IN_REGION

    def cost_micros(self, input_tokens: int, output_tokens: int) -> int:
        """Cost of one call from the provider's usage counts, rounded up to a micro-dollar."""
        input_cost = input_tokens * self.input_micros_per_1k
        output_cost = output_tokens * self.output_micros_per_1k
        return -(-(input_cost + output_cost) // 1000)


def billed_output_tokens(usage_meta: dict[str, object]) -> int:
    """Output as the provider bills it: the answer's tokens plus any thinking tokens."""
    answer = int(str(usage_meta.get("candidatesTokenCount", 0)))
    thinking = int(str(usage_meta.get("thoughtsTokenCount", 0)))
    return answer + thinking


FLASH = ModelSpec("gemini-3.6-flash", 750, 3_750, 1_048_576, thinking_level="minimal")
EMBEDDING = ModelSpec("gemini-embedding-001", 150, 0, 2_048)

REGISTER = MappingProxyType(
    {
        ModelAlias.TEXT_DEFAULT: FLASH,
        ModelAlias.TEXT_FAST: FLASH,
        ModelAlias.EMBED_DEFAULT: EMBEDDING,
        ModelAlias.GRADER_DEFAULT: FLASH,
    }
)
KNOWN_IDS = MappingProxyType({spec.model_id: spec for spec in (FLASH, EMBEDDING)})
TEXT_IDS = frozenset({FLASH.model_id})
EMBEDDING_IDS = frozenset({EMBEDDING.model_id})
