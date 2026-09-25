"""The rule vocabulary as data: every list a check reads lives here, once."""

from pathlib import Path

SRC = Path("src/catalyst_ai")
TESTS = Path("tests")
TOOLS = Path("tools")
EVALS = Path("evals")
API_DOCUMENT = Path("api/openapi.yaml")
MIGRATIONS = Path("db/migrations")
QUERIES = SRC / "platform" / "storage" / "queries"
LEDGERS = Path("docs/04-ledgers")
ARCHITECTURE_TESTS = TESTS / "architecture"
CONTRACT_TESTS = TESTS / "contract"
UNIT_TESTS = TESTS / "unit"
FIXTURES = TESTS / "fixtures"
WORKFLOW = Path(".github/workflows/ci.yml")
SESSIONS = Path("brain/sessions")
CHANGELOG = LEDGERS / "contracts-changelog.md"
INVARIANTS = LEDGERS / "invariants.md"
CONFIG_LEDGER = LEDGERS / "config.md"
REGISTER = Path("docs/03-adr/ADR-003-dependency-policy.md")
PROVIDERS_LEDGER = LEDGERS / "providers.md"

CODE_ROOTS = (SRC, TOOLS, TESTS)
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        ".tools",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "plants",
    }
)

FILE_BUDGET = 300
FUNCTION_BUDGET = 50
ROUTE_STATEMENT_BUDGET = 6
PACKAGE_SIZE_REPORT = 10
DUPLICATE_WINDOW = 6
DIRECTIVE_BASELINE = 4
JOB_LINE_MS = 20_000

BANNED_STEMS = frozenset(
    {
        "service",
        "manager",
        "helper",
        "helpers",
        "util",
        "utils",
        "common",
        "base",
        "misc",
        "shared",
        "data",
        "index",
        "core",
        "lib",
        "types",
        "v2",
        "new",
        "final",
        "temp",
        "tmp",
        "stuff",
        "orchestrator",
        "chain",
        "graph",
        "facade",
        "gateway",
        "usecase",
    }
)
BANNED_SUFFIXES = ("Impl", "Service", "Manager", "Helper", "Util", "Handler")
MODELS_FILE = "models.py"

CONTENT_LOG_KEYS = frozenset(
    {
        "text",
        "prompt",
        "completion",
        "content",
        "description",
        "comment",
        "body",
        "input",
        "output",
        "question",
        "answer",
        "document",
        "email",
        "name",
        "token",
        "secret",
        "password",
        "api_key",
        "authorization",
    }
)
RESTRICTED = "RESTRICTED"
DATA_CLASSES = frozenset({"PUBLIC", "INTERNAL", "CONFIDENTIAL", RESTRICTED})

PRODUCT_TABLE_PREFIXES = (
    "ph_",
    "tm_",
    "rh_",
    "kb_",
    "brd_",
    "wiki_",
    "standups",
    "standup_",
    "incidents",
    "incident_",
)
PRODUCT_DATABASE_MARKERS = (
    "supabase",
    "product_database",
    "PRODUCT_DATABASE",
    "BACKEND_URL",
    "backend_url",
)
BACKEND_CALL_MARKERS = ("callback_url", "webhook_url", "BACKEND_TOKEN")

MODEL_ID_PATTERNS = (
    r"gemini-\d",
    r"gemini-[a-z-]*latest",
    r"gpt-\d",
    r"claude-\d",
    r"text-embedding-",
    r"llama",
    r"mistral-",
)
UNSTABLE_MODEL_ID = r"-latest\b|-preview\b|-exp\b"
PROMPT_MARKERS = ("You are ", "Rewrite ", "Return JSON", "Respond ", "Summarize ", "Translate ")
PROMPT_MIN_LENGTH = 40
PROMPT_HEADER_KEYS = ("capability", "version", "model_alias", "tuned_on", "eval_set", "score")
PIPELINE_STAGES = (
    "parse",
    "validate",
    "retrieve",
    "assemble",
    "call",
    "validate_output",
    "postprocess",
)
PIPELINE_OPTIONAL_STAGES = frozenset({"retrieve"})
PIPELINE_GENERATION_STAGES = frozenset({"assemble", "call", "validate_output"})
PORT_CALLS = ("generate", "stream", "embed")

SEAMS = frozenset({"Provider", "Storage", "JobStore", "Clock", "Cache"})
WIRING_MODULES = frozenset({"__init__.py", "app.py", "cli.py", "descriptor.py"})
PARSER_MARKERS = ("retrieval/parsers/", "retrieval/chunking.py", "_parser.py")

INLINE_BANNED_CALLS = (
    "datetime.now",
    "datetime.utcnow",
    "time.time",
    "uuid.uuid4",
    "random.random",
)
INLINE_ALLOWED_PACKAGES = (SRC / "platform" / "clock", SRC / "platform" / "ids")
UNTYPED_ALLOWED_PACKAGES = (
    SRC / "providers",
    SRC / "retrieval" / "parsers",
    SRC / "platform" / "storage",
)

DIRECTIVE_REASONS = (
    "the listen address is configuration",
    "provider SDK ships no py.typed",
    "test double",
    "pydantic validator signature",
    "the JSON line holds heterogeneous extras",
    "starlette typing gap",
    "pinned GitHub release URL",
    "the visitor API names the method",
    "pydantic-settings reads the environment",
    "jitter, not cryptography",
)

COVERAGE_FLOORS = (
    ("src/catalyst_ai/platform/safety/", 100.0),
    ("src/catalyst_ai/platform/tenancy/", 100.0),
    ("src/catalyst_ai/platform/budgets/", 100.0),
    ("src/catalyst_ai/platform/cache/", 100.0),
    ("src/catalyst_ai/platform/auth/", 100.0),
    ("src/catalyst_ai/config/", 100.0),
    ("src/catalyst_ai/contract/", 95.0),
    ("src/catalyst_ai/capabilities/", 95.0),
    ("src/catalyst_ai/retrieval/parsers/", 80.0),
    ("src/catalyst_ai/retrieval/", 95.0),
    ("src/catalyst_ai/providers/port.py", 90.0),
    ("src/catalyst_ai/providers/", 80.0),
    ("src/catalyst_ai/platform/storage/", 80.0),
    ("src/catalyst_ai/platform/", 90.0),
)
COVERAGE_OVERALL = 90.0
COVERAGE_EXCLUDED = ("src/catalyst_ai/app.py", "src/catalyst_ai/cli.py")

GENERATED_PATHS = ("uv.lock", "api/openapi.yaml", "tests/fixtures/providers/")
GENERATED_LEDGERS = ("capabilities.md", "errors.md", "config.md", "providers.md", "eval-sets.md")

DOCKERFILE = Path("Dockerfile")
MAKEFILE = Path("Makefile")
DOCKERFILE_CI = Path("Dockerfile.ci")
BASE_IMAGE = (
    "python:3.12.14-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9"
)
CI_IMAGE = BASE_IMAGE

WORKFLOWS = WORKFLOW.parent
CI_JOB = "verify"
CI_TRIGGERS: dict[str, object] = {"push": {"branches": ["main"]}}
CI_DATABASE_IMAGE = (
    "pgvector/pgvector:0.8.1-pg17"
    "@sha256:3e8b3adfd27b5707128f60956f62a793c3c9326ea8cfaf0eab7adccb5d700b21"
)
CI_PGVECTOR = "0.8.1"
CI_DATABASE_ALIAS = "postgres"
CI_DATABASE_ENV = {
    "POSTGRES_USER": "catalyst_ai",
    "POSTGRES_PASSWORD": "catalyst_ai",
    "POSTGRES_DB": "catalyst_ai",
}
CI_DATABASE_OPTIONS = (
    '--health-cmd "pg_isready -U catalyst_ai" --health-interval 5s --health-timeout 5s'
    " --health-retries 10"
)
CI_JOB_ENV = {
    "CATALYST_AI_EVAL_DATABASE_URL": "postgresql://catalyst_ai:catalyst_ai@postgres:5432/catalyst_ai"
}
CI_NETWORK = "catalyst-ai-ci"

CI_IMAGE_WORKFLOW = WORKFLOWS / "ci-image.yml"
CI_IMAGE_JOB = "image"
CI_IMAGE_TRIGGERS: dict[str, object] = {
    "push": {"branches": ["main"], "paths": [DOCKERFILE_CI.as_posix()]}
}
CI_IMAGE_PERMISSIONS = {"contents": "read", "packages": "write"}
CI_IMAGE_JOB_ENV = {"GITHUB_TOKEN": "${{ github.token }}"}
CI_IMAGE_SETUP = "pip install uv==0.12.16"
CI_IMAGE_ALLOWED_RUNS = (CI_IMAGE_SETUP, "make ci-image", "make ci-cold", "make ci-image-push")
CI_REGISTRY = "ghcr.io"
CI_IMAGE_LABEL = "org.catalyst-ai.dockerfile-sha256"
CI_IMAGE_BUILT_FROM: str | None = None

RELEASE_WORKFLOW = WORKFLOWS / "release.yml"
RELEASE_JOB = "release"
RELEASE_TRIGGERS: dict[str, object] = {"push": {"branches": ["main"]}}
RELEASE_PERMISSIONS = {"contents": "read", "id-token": "write"}
RELEASE_JOB_ENV = {
    name: "${{ vars." + name + " }}"
    for name in (
        "RELEASE_REGISTRY",
        "RELEASE_LOCATION",
        "RELEASE_WIF_PROVIDER",
        "RELEASE_SERVICE_ACCOUNT",
    )
}
RELEASE_ALLOWED_RUNS = (CI_IMAGE_SETUP, "make release RELEASE_FLAGS=--print")

CI_ALLOWED_USES = ("actions/checkout@v4",)
CI_SETUP = (
    "apt-get update && apt-get install -y --no-install-recommends make git curl ca-certificates"
    " && pip install uv==0.12.16 && git config --global --add safe.directory '*'"
)
CI_ALLOWED_RUNS = (
    CI_SETUP,
    "make tools",
    "make hooks",
    "make verify",
)
NIGHTLY_WORKFLOW = WORKFLOWS / "nightly.yml"
NIGHTLY_JOB = "nightly"
NIGHTLY_TRIGGERS: dict[str, object] = {
    "schedule": [{"cron": "0 2 * * *"}],
    "workflow_dispatch": None,
}
NIGHTLY_ALLOWED_RUNS = (CI_SETUP, "make tools", "make nightly")
NIGHTLY_SCAN_JOB = "image-scan"
NIGHTLY_SCAN_RUNS = (CI_IMAGE_SETUP, "make tools", "make scan-tools", "make image-scan")

LICENSE_ALLOWLIST = (
    "MIT",
    "BSD",
    "Apache",
    "PSF",
    "ISC",
    "MPL",
    "Python Software Foundation",
    "Unlicense",
    "0BSD",
)

RADII = ("LOCAL", "CAPABILITY", "CONTRACT", "PLATFORM", "SYSTEM")
SYSTEM_PATHS = (
    "src/catalyst_ai/contract/envelopes.py",
    "src/catalyst_ai/contract/errors.py",
    "src/catalyst_ai/providers/port.py",
    "src/catalyst_ai/platform/tenancy/",
    "src/catalyst_ai/platform/safety/",
    "db/migrations/",
)
PLATFORM_PATHS = (
    "src/catalyst_ai/platform/",
    "src/catalyst_ai/providers/",
    "src/catalyst_ai/retrieval/",
    "src/catalyst_ai/config/",
)
CONTRACT_PATHS = ("src/catalyst_ai/contract/", "api/openapi.yaml")
CAPABILITY_PATHS = ("src/catalyst_ai/capabilities/", "evals/")
READ_ONLY_CAPABILITIES = ("assistant",)
