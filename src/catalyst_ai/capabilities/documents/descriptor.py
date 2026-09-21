"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "documents"
version = "1.0.0"
prompt_version = "1"
eval_set_version = "1"
kind = "sync"
alias = "text-default"
p95_latency_ms = 15_000
p95_cost_micros = 8_000
timeout_ms = 20_000
cache_ttl_seconds = 600
temperature = 0.2
max_output_tokens = 6_000
kill_switch = "CATALYST_AI_CAPABILITY_DOCUMENTS_ENABLED"
retires = (
    "kb-train",
    "folio-ai-search",
    "docintel-ingest",
    "docintel-analyze",
    "docintel-ask",
    "docintel-generate",
    "docintel-sync",
)
