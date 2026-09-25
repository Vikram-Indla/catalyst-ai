"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "generate-tests"
version = "1.0.0"
prompt_version = "1"
eval_set_version = "1"
kind = "sync"
alias = "text-default"
p95_latency_ms = 12_000
p95_cost_micros = 8_000
timeout_ms = 20_000
cache_ttl_seconds = 3_600
temperature = 0.3
max_output_tokens = 8_000
kill_switch = "CATALYST_AI_CAPABILITY_GENERATE_TESTS__ENABLED"
retires = ("ai-generate-story-test-cases", "ai-generate-test-artefacts")
