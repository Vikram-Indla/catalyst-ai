"""search: the retrieval operations — index documents, forget them, find similar ones."""

from catalyst_ai.capabilities.search.indexing import run_delete, run_upsert
from catalyst_ai.capabilities.search.pipeline import run
from catalyst_ai.capabilities.search.routes import router

__all__ = ["router", "run", "run_delete", "run_upsert"]
