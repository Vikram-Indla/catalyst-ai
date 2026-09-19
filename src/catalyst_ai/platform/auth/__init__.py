"""Service-token verification for every operation of the contract."""

from catalyst_ai.platform.auth.middleware import ServiceTokenMiddleware, verify_token

__all__ = ["ServiceTokenMiddleware", "verify_token"]
