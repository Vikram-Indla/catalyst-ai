"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "generate-children"
version = "1.1.0"
prompt_version = "2"
eval_set_version = "2"
kind = "sync"
alias = "text-default"
p95_latency_ms = 8_000
p95_cost_micros = 6_000
timeout_ms = 20_000
cache_ttl_seconds = 3_600
temperature = 0.4
max_output_tokens = 6_000
kill_switch = "CATALYST_AI_CAPABILITY_GENERATE_CHILDREN__ENABLED"
retires = ("ai-generate-stories", "ai-generate-epics", "ai-suggest-children")
