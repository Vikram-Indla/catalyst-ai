"""propose-workflow: a described process becomes a scheme the backend validates and installs."""

from catalyst_ai.capabilities.propose_workflow.pipeline import run
from catalyst_ai.capabilities.propose_workflow.routes import router

__all__ = ["router", "run"]
