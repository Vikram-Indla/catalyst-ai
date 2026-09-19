"""The register's Gemini rows: alias → concrete id, prices, context and the retention setting."""

from dataclasses import dataclass
from types import MappingProxyType

from catalyst_ai.providers.port import ModelAlias

PROVIDER = "gemini"
RETENTION = "paid tier of the Gemini API: prompts and completions are not used to train models"


@dataclass(frozen=True)
class ModelSpec:
    """One concrete model and what it costs; prices in micro-dollars per 1 000 tokens."""

    model_id: str
    input_micros_per_1k: int
    output_micros_per_1k: int
    context_tokens: int

    def cost_micros(self, input_tokens: int, output_tokens: int) -> int:
        """Cost of one call from the provider's usage counts, rounded up to a micro-dollar."""
        input_cost = input_tokens * self.input_micros_per_1k
        output_cost = output_tokens * self.output_micros_per_1k
        return -(-(input_cost + output_cost) // 1000)


FLASH = ModelSpec("gemini-2.5-flash", 300, 2_500, 1_048_576)
FLASH_LITE = ModelSpec("gemini-2.5-flash-lite", 100, 400, 1_048_576)
PRO = ModelSpec("gemini-2.5-pro", 1_250, 10_000, 1_048_576)
EMBEDDING = ModelSpec("gemini-embedding-001", 150, 0, 2_048)

REGISTER = MappingProxyType(
    {
        ModelAlias.TEXT_DEFAULT: FLASH,
        ModelAlias.TEXT_FAST: FLASH_LITE,
        ModelAlias.TEXT_LONG: PRO,
        ModelAlias.EMBED_DEFAULT: EMBEDDING,
        ModelAlias.GRADER_DEFAULT: FLASH,
    }
)
KNOWN_IDS = MappingProxyType({spec.model_id: spec for spec in (FLASH, FLASH_LITE, PRO, EMBEDDING)})
