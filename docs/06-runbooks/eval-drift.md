# Eval drift — refusals rise, or a score falls below its floor

**Alert:** `OutputRefusalsHigh` (production); the gate's eval step (a change).

## The two ways this arrives

1. **In the gate**, as a red `make verify`: a grader under its floor in `thresholds.yaml`. The
   change that lowered it is in front of you; that is the good case.
2. **In production**, as `OutputRefusalsHigh`: more than one answer in a hundred refused as
   `ai.output.invalid` or `ai.output.unsafe`. Nothing changed here — so the model did.

## The first three commands

1. `sum by (code) (rate(catalyst_ai_errors_total{code=~"ai.output.*"}[6h]))` — `invalid` is a
   schema or a citation failure, `unsafe` is the leakage scanner. They have different causes.
2. `sum by (capability, model) (rate(catalyst_ai_provider_calls_total[6h]))` — which model is
   actually serving. A provider that silently moved an alias to a new snapshot is the usual
   cause of a refusal rise with no deploy.
3. `make evals CAP=<capability>` on the recorded fixtures: green means the pipeline is fine and
   the live model drifted; red means the fixtures already caught it.

## What to do

- Re-record the capability's fixtures against the live model (`make record LIVE=1 CAP=<name>`,
  with a key) and run its set. The numbers go in a session record either way.
- If the set is now below its floor: that is a model regression. Pin the previous model id in
  configuration (the register's alias mapping), open a `D-` row for the pin, and re-run.
- A floor is never lowered to make a run pass. Lowering one is a `D-` row with the evidence and
  the lead's yes (`RULE-000 §3`).

## When to disable a capability

When refusals are the majority for one capability and a pin is not available within the hour:
disable it (`kill-switch.md`) rather than serve a stream of refusals; the backend shows the
feature as unavailable instead of broken.

## When to page

Only if the refusals are `ai.output.unsafe` in volume — that is content trying to leave that
should not, and it wants eyes immediately. A rise in `invalid` is a ticket.
