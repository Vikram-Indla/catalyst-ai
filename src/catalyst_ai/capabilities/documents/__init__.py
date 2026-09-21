"""documents: hostile files parsed under limits, indexed per space, asked and drafted, cited."""

from catalyst_ai.capabilities.documents.ask import run as ask
from catalyst_ai.capabilities.documents.drafting import run as generate
from catalyst_ai.capabilities.documents.ingest import run_ingest
from catalyst_ai.capabilities.documents.routes import router

__all__ = ["ask", "generate", "router", "run_ingest"]
