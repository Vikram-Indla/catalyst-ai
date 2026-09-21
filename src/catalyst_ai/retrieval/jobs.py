"""The two maintenance jobs: re-embed after a model change; forget what stopped arriving."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from catalyst_ai.contract.search import IndexDocument
from catalyst_ai.platform.clock import Clock
from catalyst_ai.platform.storage import RetentionCut, Storage, StorageUnavailableError
from catalyst_ai.providers.port import Provider
from catalyst_ai.retrieval.corpora import CorpusSpec
from catalyst_ai.retrieval.ingest import Job, index_unavailable, upsert

JOB_CAPABILITY = "search"
BATCH = 50
REEMBED_TIMEOUT_MS = 60_000
NO_LIMIT = 10**9


@dataclass(frozen=True)
class Report:
    """What a job did: organisations visited, documents touched."""

    organizations: int
    documents: int


async def _reembed_organization(
    organization_id: UUID, spec: CorpusSpec, storage: Storage, provider: Provider
) -> int:
    model = provider.model_id(spec.alias)
    job = Job(organization_id, spec, JOB_CAPABILITY, REEMBED_TIMEOUT_MS, max_chunks=NO_LIMIT)
    done = 0
    while True:
        stale = await storage.stale_documents(
            organization_id, spec.name, model, spec.version, BATCH
        )
        if not stale:
            return done
        documents = []
        for external_id in stale:
            record = await storage.read_document(organization_id, spec.name, external_id)
            if record is not None:
                documents.append(
                    IndexDocument(
                        external_id=record.external_id,
                        kind=record.kind,
                        title=record.title,
                        text=record.text,
                        data_class=record.data_class,
                        content_hash=record.content_hash,
                    )
                )
        outcome = await upsert(job, documents, storage, provider)
        done += sum(1 for result in outcome.results if not result.unchanged)


async def reembed(spec: CorpusSpec, storage: Storage, provider: Provider) -> Report:
    """Bring every organisation's documents to the current model and version, batch by batch."""
    try:
        organizations = await storage.organizations(spec.name)
        documents = 0
        for organization_id in organizations:
            documents += await _reembed_organization(organization_id, spec, storage, provider)
    except StorageUnavailableError as error:
        raise index_unavailable(error) from error
    return Report(len(organizations), documents)


async def retention(spec: CorpusSpec, storage: Storage, clock: Clock, ttl_days: int) -> Report:
    """Forget documents the backend has not sent for longer than the time to live."""
    before = clock.now() - timedelta(days=ttl_days)
    try:
        organizations = await storage.organizations(spec.name)
        documents = 0
        for organization_id in organizations:
            while True:
                cut = RetentionCut(organization_id, spec.name, before, BATCH)
                expired = await storage.expired_documents(cut)
                if not expired:
                    break
                await storage.delete_documents(organization_id, spec.name, expired)
                documents += len(expired)
    except StorageUnavailableError as error:
        raise index_unavailable(error) from error
    return Report(len(organizations), documents)
