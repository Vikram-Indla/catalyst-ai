"""release-notes: notes or an overview from a supplied change list, every entry traced to an id."""

from catalyst_ai.capabilities.release_notes.pipeline import run
from catalyst_ai.capabilities.release_notes.routes import router

__all__ = ["router", "run"]
