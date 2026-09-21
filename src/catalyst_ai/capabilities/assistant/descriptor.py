"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "assistant"
version = "1.0.0"
prompt_version = "1"
eval_set_version = "1"
kind = "stream"
alias = "text-default"
p95_latency_ms = 12_000
p95_cost_micros = 6_000
timeout_ms = 20_000
cache_ttl_seconds = 300
temperature = 0.3
max_output_tokens = 4_000
kill_switch = "CATALYST_AI_CAPABILITY_ASSISTANT_ENABLED"
retires = ("caty-chat", "ai-admin-assistant", "ai-tm-assist")
