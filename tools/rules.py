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
    r"gpt-\d",
    r"claude-\d",
    r"text-embedding-",
    r"llama",
    r"mistral-",
)
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

SEAMS = frozenset({"Provider", "Storage", "Clock", "Cache"})
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
