"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "interpret-query"
version = "1.1.0"
prompt_version = "2"
eval_set_version = "2"
kind = "sync"
alias = "text-fast"
p95_latency_ms = 4_000
p95_cost_micros = 2_000
timeout_ms = 10_000
cache_ttl_seconds = 600
temperature = 0.0
max_output_tokens = 400
kill_switch = "CATALYST_AI_CAPABILITY_INTERPRET_QUERY__ENABLED"
retires = ("ai-search-issues",)
