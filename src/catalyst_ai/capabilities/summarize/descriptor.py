"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "summarize"
version = "1.1.0"
prompt_version = "2"
eval_set_version = "2"
kind = "sync"
alias = "text-default"
p95_latency_ms = 8_000
p95_cost_micros = 4_000
timeout_ms = 20_000
cache_ttl_seconds = 900
temperature = 0.3
max_output_tokens = 1_500
kill_switch = "CATALYST_AI_CAPABILITY_SUMMARIZE_ENABLED"
retires = ("summarize-comments", "chat-summarize")
