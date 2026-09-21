"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "translate"
version = "1.0.0"
prompt_version = "1"
eval_set_version = "1"
kind = "sync"
alias = "text-fast"
p95_latency_ms = 6_000
p95_cost_micros = 2_000
timeout_ms = 15_000
cache_ttl_seconds = 86_400
temperature = 0.1
max_output_tokens = 8_000
kill_switch = "CATALYST_AI_CAPABILITY_TRANSLATE_ENABLED"
retires = ("ai-translate-field", "ai-translate-title", "ai-improve-story mode translate_text")
