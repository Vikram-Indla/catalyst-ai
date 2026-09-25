"""Settings: every variable declared with its type, validation, data class and description."""

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, EnvSettingsSource, SettingsConfigDict

from catalyst_ai.config.deployed import start_problem
from catalyst_ai.config.pins import ModelPins
from catalyst_ai.config.residency import DEVELOPMENT_LOCATION, regional_endpoint
from catalyst_ai.config.unknown import refuse_unknown
from catalyst_ai.contract.models import TextAlias, available

ENV_PREFIX = "CATALYST_AI_"
NESTING = "__"
MIN_KEYS = 1
MAX_KEYS = 2
PUBLIC_KEY_BYTES = 32
MAX_SKEW_S = 60
MAX_TTL_S = 300
MAX_JOB_TIMEOUT_S = 3_600
MAX_WORKER_CONCURRENCY = 64


@dataclass(frozen=True)
class PublicKeyEntry:
    """One configured verification key: its id and its 32 raw bytes."""

    key_id: str
    raw: bytes


def _public_key_entry(entry: str) -> PublicKeyEntry:
    key_id, separator, encoded = entry.strip().partition(":")
    if not separator or not key_id or not encoded:
        message = "a public key entry is kid:base64url"
        raise ValueError(message)
    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, UnicodeEncodeError) as error:
        message = f"public key {key_id} is not base64url"
        raise ValueError(message) from error
    if len(raw) != PUBLIC_KEY_BYTES:
        message = f"public key {key_id} is not {PUBLIC_KEY_BYTES} bytes"
        raise ValueError(message)
    return PublicKeyEntry(key_id, raw)


def parse_public_keys(text: str) -> list[PublicKeyEntry]:
    """Parse `kid:base64url[,kid:base64url]` into one or two entries with distinct ids."""
    entries = [_public_key_entry(entry) for entry in text.split(",") if entry.strip()]
    if not MIN_KEYS <= len(entries) <= MAX_KEYS:
        message = f"expected {MIN_KEYS}..{MAX_KEYS} public keys, got {len(entries)}"
        raise ValueError(message)
    if len({entry.key_id for entry in entries}) != len(entries):
        message = "public key ids must be distinct"
        raise ValueError(message)
    return entries


class Environment(StrEnum):
    """Return the deployment the process runs in."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Minimum log level."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


def _addr(value: str) -> str:
    host, sep, port = value.rpartition(":")
    if not sep or not port.isdigit():
        message = f"expected host:port, got {value!r}"
        raise ValueError(message)
    return f"{host}:{port}"


class CapabilitySettings(BaseModel):
    """The per-capability knobs an operator may turn without a deploy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: Annotated[bool, Field(description="PUBLIC · The kill switch")] = True
    model_alias: Annotated[
        Annotated[TextAlias, AfterValidator(available)] | None,
        Field(description="PUBLIC · This capability's alias, over the environment's default"),
    ] = None
    cache_ttl_seconds: Annotated[
        int | None, Field(ge=0, description="PUBLIC · Overrides the descriptor's cache TTL")
    ] = None
    timeout_ms: Annotated[
        int | None, Field(gt=0, description="PUBLIC · Overrides the descriptor's per-call deadline")
    ] = None


class Settings(BaseSettings, ModelPins):
    """Hold the process configuration, read once at startup; the config ledger mirrors it."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX, env_nested_delimiter=NESTING, extra="forbid", frozen=True
    )

    environment: Annotated[
        Environment, Field(description="PUBLIC · The deployment the process runs in")
    ]
    auth_public_keys: Annotated[
        str,
        Field(
            description="INTERNAL · The backend's Ed25519 public keys, kid:base64url, two at most"
        ),
    ]
    auth_clock_skew_seconds: Annotated[
        int,
        Field(ge=0, le=MAX_SKEW_S, description="PUBLIC · Tolerated drift between the two clocks"),
    ] = 5
    auth_max_ttl_seconds: Annotated[
        int,
        Field(gt=0, le=MAX_TTL_S, description="PUBLIC · A request envelope may live this long"),
    ] = 60
    database_url: Annotated[
        SecretStr,
        Field(description="RESTRICTED · serve's login: a member of the application role only"),
    ]
    database_worker_url: Annotated[
        SecretStr | None,
        Field(description="RESTRICTED · The worker's login: application and maintenance roles"),
    ] = None
    database_migrate_url: Annotated[
        SecretStr | None,
        Field(description="RESTRICTED · The owner's login, for `catalyst-ai migrate` alone"),
    ] = None
    database_pool_max: Annotated[
        int, Field(gt=0, description="PUBLIC · Connections in the pool at most")
    ] = 8
    http_addr: Annotated[str, Field(description="PUBLIC · The contract listen address")] = ":8090"
    ops_addr: Annotated[str, Field(description="PUBLIC · /healthz, /readyz, metrics")] = ":9091"
    shutdown_drain_seconds: Annotated[
        int,
        Field(gt=0, description="PUBLIC · In-flight requests may finish after SIGTERM"),
    ] = 10
    log_level: Annotated[LogLevel, Field(description="PUBLIC · Minimum log level")] = LogLevel.INFO
    capabilities_enabled: Annotated[
        bool,
        Field(description="PUBLIC · Every capability at once; off, each refuses as disabled"),
    ] = True
    otel_exporter_endpoint: Annotated[
        str | None,
        Field(description="INTERNAL · Where traces and metrics go; required in production"),
    ] = None
    tenant_budget_default_micros_per_day: Annotated[
        int, Field(gt=0, description="PUBLIC · Per-organisation daily spend cap unless overridden")
    ] = 5_000_000
    tenant_concurrency_max: Annotated[
        int, Field(gt=0, description="PUBLIC · Concurrent provider calls per organisation")
    ] = 8
    job_result_ttl_seconds: Annotated[
        int, Field(gt=0, description="PUBLIC · Job results expire after this")
    ] = 86_400
    job_timeout_seconds: Annotated[
        int, Field(gt=0, le=MAX_JOB_TIMEOUT_S, description="PUBLIC · A job's execution deadline")
    ] = 600
    worker_concurrency: Annotated[
        int,
        Field(gt=0, le=MAX_WORKER_CONCURRENCY, description="PUBLIC · Jobs one worker runs at once"),
    ] = 4
    worker_concurrency_per_organization: Annotated[
        int,
        Field(
            gt=0, le=MAX_WORKER_CONCURRENCY, description="PUBLIC · Jobs of one organisation at once"
        ),
    ] = 2
    provider_log_retention_days: Annotated[
        int, Field(gt=0, description="PUBLIC · provider_calls retention")
    ] = 90
    retrieval_index_max_chunks_per_organization: Annotated[
        int, Field(gt=0, description="PUBLIC · An organisation's corpus size in chunks at most")
    ] = 500_000
    retrieval_document_ttl_days: Annotated[
        int,
        Field(gt=0, description="PUBLIC · The retention job forgets documents unseen this long"),
    ] = 400
    provider_access_token: Annotated[
        SecretStr | None,
        Field(description="RESTRICTED · A developer's own short-lived token; development only"),
    ] = None
    provider_gemini_base_url: Annotated[
        str | None,
        Field(
            pattern=r"^https://",
            description="INTERNAL · Overrides the location's origin; development only",
        ),
    ] = None
    provider_vertex_location: Annotated[
        str | None,
        Field(description="INTERNAL · The in-Kingdom region calls go to; required when deployed"),
    ] = None
    provider_vertex_project: Annotated[
        str, Field(max_length=64, description="INTERNAL · The project the provider bills and runs")
    ] = ""
    model_text_alias: Annotated[
        TextAlias,
        AfterValidator(available),
        Field(
            description=(
                "PUBLIC · The alias a capability asking for text gets in this environment; "
                "the register resolves it to a model and its price. The default is the row the "
                "sets were measured on; a deployment may select a cheaper one"
            )
        ),
    ] = TextAlias.TEXT_DEFAULT
    capability_improve_story: Annotated[
        CapabilitySettings, Field(description="PUBLIC · improve-story: enabled, cache TTL, timeout")
    ] = CapabilitySettings()
    capability_generate_children: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · generate-children: enabled, cache TTL, timeout"),
    ] = CapabilitySettings()
    capability_release_notes: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · release-notes: enabled, cache TTL, timeout"),
    ] = CapabilitySettings()
    capability_documents: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · documents: enabled, cache TTL, the parse and call timeout"),
    ] = CapabilitySettings()
    capability_assistant: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · assistant: enabled, cache TTL of the whole form, timeout"),
    ] = CapabilitySettings()
    capability_unfurl: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · unfurl: enabled, cache TTL, timeout"),
    ] = CapabilitySettings()
    capability_interpret_query: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · interpret-query: enabled, cache TTL, timeout"),
    ] = CapabilitySettings()
    capability_brief: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · brief: enabled, cache TTL, timeout"),
    ] = CapabilitySettings()
    capability_generate_tests: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · generate-tests: enabled, cache TTL, timeout"),
    ] = CapabilitySettings()
    capability_post_mortem: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · post-mortem: enabled, cache TTL, timeout"),
    ] = CapabilitySettings()
    capability_propose_workflow: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · propose-workflow: enabled, cache TTL, timeout"),
    ] = CapabilitySettings()
    capability_search: Annotated[
        CapabilitySettings,
        Field(description="PUBLIC · search and the index operations: enabled, cache TTL, timeout"),
    ] = CapabilitySettings()
    capability_summarize: Annotated[
        CapabilitySettings, Field(description="PUBLIC · summarize: enabled, cache TTL, timeout")
    ] = CapabilitySettings()
    capability_translate: Annotated[
        CapabilitySettings, Field(description="PUBLIC · translate: enabled, cache TTL, timeout")
    ] = CapabilitySettings()

    def capability(self, name: str) -> CapabilitySettings:
        """Return one capability's knobs by name; an unknown name gets the defaults."""
        field = f"capability_{name.replace('-', '_')}"
        knobs = getattr(self, field, None)
        return knobs if isinstance(knobs, CapabilitySettings) else CapabilitySettings()

    @field_validator("auth_public_keys")
    @classmethod
    def _well_formed_keys(cls, value: str) -> str:
        parse_public_keys(value)
        return value

    @field_validator("database_url", "database_worker_url", "database_migrate_url")
    @classmethod
    def _postgres_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value
        raw = value.get_secret_value()
        if not raw.startswith(("postgres://", "postgresql://")) or "@" not in raw:
            message = "DATABASE_URL must be a postgres:// URL with a host"
            raise ValueError(message)
        return value

    @field_validator("http_addr", "ops_addr")
    @classmethod
    def _host_port(cls, value: str) -> str:
        return _addr(value)

    @model_validator(mode="after")
    def _ports_differ(self) -> Self:
        problem = start_problem(self)
        if problem is not None:
            raise ValueError(problem)
        return self

    def provider_location(self) -> str:
        """Return the configured region; development falls back to the first allowed one."""
        return self.provider_vertex_location or DEVELOPMENT_LOCATION

    def provider_origin(self) -> str:
        """Return the provider's origin: the override (development), else the region's own."""
        return self.provider_gemini_base_url or regional_endpoint(self.provider_location())


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read the environment once; a missing, invalid or unknown variable stops the process."""
    read = EnvSettingsSource(Settings).env_vars if environ is None else environ
    refuse_unknown(read, Settings, ENV_PREFIX, NESTING)
    return Settings()  # type: ignore[call-arg]  # pydantic-settings reads the environment
