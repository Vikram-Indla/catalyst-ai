---
id: ARCH-010
title: Observability without content
status: Locked
version: 1.1.0
owner: AI service lead
created: 2026-09-18
---

# ARCH-010 — Observability without content

## 1. Every call is a row, never a transcript

Every provider call writes one `provider_calls` row and one structured log line:
`organization_id`, `capability`, `capability_version`, `prompt_version`, `model` (alias and
concrete id), `input_tokens`, `output_tokens`, `cost_micros`, `latency_ms`, `cache_hit`,
`outcome` (`ok` / error code), `request_id`. Never the prompt, never the completion, never a
request field of class `CONFIDENTIAL` or above. `tools/checks/logs` greps every logging call
for content-shaped keys (`text`, `prompt`, `completion`, `content`, `description`, `message`
when it is a request field) and fails on one.

## 2. Metrics and traces

`platform/observability` exposes, on the ops port: request RED metrics per operation; provider
calls, tokens, cost and latency per capability, model and organisation; cache hits and misses;
budget refusals; circuit state per provider; job queue depth and age. Traces span the pipeline
stages by name (`parse` … `postprocess`) with attributes limited to the row in §1. OpenTelemetry
is the only exporter; vendor SDKs are not register rows. The ops port serves them as the
Prometheus text exposition format at `/metrics` — the format every collector, including the
OpenTelemetry collector, scrapes without translation (`D-039`); the contract port serves no
metrics. The objectives those numbers answer to are `docs/04-ledgers/slos.md`, the rules over
them `ops/alerts.yaml`, and every rule names a runbook.

## 3. Logs

Structured JSON through the standard library's `logging` with one formatter in
`platform/observability`; `print` fails `ruff` (`T20`). The redacting filter drops any field
named in the `RESTRICTED` and `CONFIDENTIAL` key lists before emission — belt to the check's
braces. Retention of `provider_calls` rows and logs is a configuration value with a platform
default; the retention job purges past it.

## 4. Quality sampling

Off by default. A per-organisation opt-in in configuration, recorded with a `D-NNN`, allows a
sampled fraction of `(input, output)` pairs to be stored for human quality review with a retention
limit; the rows are tenant-scoped and purged on expiry. No such opt-in exists at the time of this
page (`Q-002`).

## 5. Runbooks

Every capability lands with a runbook line in `docs/06-runbooks/`: what to check when quality
drops (eval drift, model change, provider status), how to disable it without a deploy (the kill
switch), and what the backend receives when it is off.
