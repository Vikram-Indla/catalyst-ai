"""A plant: the assistant reaching for a client and a writer."""

import httpx

from catalyst_ai.retrieval.ingest import upsert


def fetch(url: str) -> None:
    httpx.get(url)
    upsert()
