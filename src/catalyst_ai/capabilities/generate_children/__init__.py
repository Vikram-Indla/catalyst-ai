"""generate-children: typed candidate children of a parent, validated against the hierarchy."""

from catalyst_ai.capabilities.generate_children.pipeline import run
from catalyst_ai.capabilities.generate_children.routes import router

__all__ = ["router", "run"]
