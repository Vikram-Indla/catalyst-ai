"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "improve-story"
version = "1.0.0"
prompt_version = "1"
eval_set_version = "1"
kind = "sync"
alias = "text-default"
p95_latency_ms = 4_000
p95_cost_micros = 2_000
timeout_ms = 10_000
cache_ttl_seconds = 3_600
temperature = 0.3
max_output_tokens = 3_000
kill_switch = "CATALYST_AI_CAPABILITY_IMPROVE_STORY_ENABLED"
retires = ("ai-improve-story",)
