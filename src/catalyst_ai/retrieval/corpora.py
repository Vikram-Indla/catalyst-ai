"""Each corpus declares its chunking, embedding alias and dimensions, revision and limit."""

from dataclasses import dataclass
from types import MappingProxyType

from catalyst_ai.contract.search import Corpus
from catalyst_ai.providers.port import ModelAlias


@dataclass(frozen=True)
class CorpusSpec:
    """The recorded chunking and embedding decision of one corpus; changing it is a re-embed."""

    name: Corpus
    alias: ModelAlias
    dimensions: int
    revision: int
    chunk_chars: int
    overlap_chars: int
    max_document_chars: int
    embed_batch: int

    @property
    def version(self) -> str:
        """The embedding version label every row carries: dimensions and the corpus revision."""
        return f"d{self.dimensions}-r{self.revision}"


WORK_ITEMS = CorpusSpec(
    name="work_items",
    alias=ModelAlias.EMBED_DEFAULT,
    dimensions=768,
    revision=1,
    chunk_chars=1_000,
    overlap_chars=120,
    max_document_chars=20_000,
    embed_batch=100,
)

CORPORA = MappingProxyType({WORK_ITEMS.name: WORK_ITEMS})


def spec_of(corpus: Corpus) -> CorpusSpec:
    """Return the declaration of a corpus."""
    return CORPORA[corpus]
