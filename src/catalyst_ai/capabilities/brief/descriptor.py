"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "brief"
version = "1.0.0"
prompt_version = "1"
eval_set_version = "1"
kind = "sync"
alias = "text-default"
p95_latency_ms = 8_000
p95_cost_micros = 4_000
timeout_ms = 15_000
cache_ttl_seconds = 900
temperature = 0.2
max_output_tokens = 2_000
kill_switch = "CATALYST_AI_CAPABILITY_BRIEF__ENABLED"
retires = ("alignment-story",)
