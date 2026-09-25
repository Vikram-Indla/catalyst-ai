"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "release-notes"
version = "1.0.0"
prompt_version = "1"
eval_set_version = "1"
kind = "sync"
alias = "text-default"
p95_latency_ms = 10_000
p95_cost_micros = 6_000
timeout_ms = 20_000
cache_ttl_seconds = 900
temperature = 0.3
max_output_tokens = 6_000
kill_switch = "CATALYST_AI_CAPABILITY_RELEASE_NOTES__ENABLED"
retires = ("release-notes-generate", "summarize-release")
