"""The capability's declaration: what the ledger, the gate and the runtime read."""

name = "propose-workflow"
version = "1.0.0"
prompt_version = "1"
eval_set_version = "1"
kind = "sync"
alias = "text-default"
p95_latency_ms = 10_000
p95_cost_micros = 6_000
timeout_ms = 20_000
cache_ttl_seconds = 600
temperature = 0.2
max_output_tokens = 6_000
kill_switch = "CATALYST_AI_CAPABILITY_PROPOSE_WORKFLOW_ENABLED"
retires = ("workflow-ai", "ai-generate-workflow")
