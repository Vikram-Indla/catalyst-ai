"""Plant."""
import logging

log = logging.getLogger(__name__)


def talk(prompt: str) -> None:
    """Leaks."""
    log.info("call", extra={"prompt": prompt})
