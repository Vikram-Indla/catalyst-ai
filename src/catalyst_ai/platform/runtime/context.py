"""The runtime context a pipeline receives: the seams, the settings and the clock."""

from dataclasses import dataclass, field

from catalyst_ai.config import Settings
from catalyst_ai.platform.budgets import TenantBudgets
from catalyst_ai.platform.cache import Cache
from catalyst_ai.platform.clock import Clock
from catalyst_ai.platform.observability.metrics import Metrics
from catalyst_ai.platform.storage import JobStore, MemoryJobStore, Storage
from catalyst_ai.providers.port import Provider


@dataclass(frozen=True)
class RuntimeContext:
    """Assembled once by the composition root; passed to every pipeline run."""

    settings: Settings
    provider: Provider
    cache: Cache
    budgets: TenantBudgets
    clock: Clock
    storage: Storage
    jobs: JobStore = field(default_factory=MemoryJobStore)
    metrics: Metrics = field(default_factory=Metrics)
