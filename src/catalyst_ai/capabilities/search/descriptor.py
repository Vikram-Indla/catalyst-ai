"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "search"
version = "1.0.0"
prompt_version = "0"
eval_set_version = "1"
kind = "sync"
alias = "embed-default"
p95_latency_ms = 800
p95_cost_micros = 400
timeout_ms = 10_000
cache_ttl_seconds = 0
kill_switch = "CATALYST_AI_CAPABILITY_SEARCH_ENABLED"
retires = ("ai-similar-items", "ai-search-issues")
corpus_default = "work_items"
