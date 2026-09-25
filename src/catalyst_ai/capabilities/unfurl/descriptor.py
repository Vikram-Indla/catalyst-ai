"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "unfurl"
version = "1.0.0"
prompt_version = "1"
eval_set_version = "1"
kind = "sync"
alias = "text-default"
p95_latency_ms = 4_000
p95_cost_micros = 1_000
timeout_ms = 10_000
cache_ttl_seconds = 3_600
temperature = 0.1
max_output_tokens = 600
kill_switch = "CATALYST_AI_CAPABILITY_UNFURL__ENABLED"
retires = ("chat-unfurl",)
