# Kill switch — disabling a capability without a deploy

**Drill:** `make drill CAP=<capability>` proves the switch on the compose stack and prints the
transcript. **Alert:** none of its own — a disabled capability is a decision, not a failure; the
capability's own alerts stop firing because no call reaches the provider.

## The mechanism

Every capability has `CATALYST_AI_CAPABILITY_<NAME>__ENABLED`. Off, the door refuses before any
retrieval or provider call with `ai.capability.disabled` (503); the backend surfaces the feature
as unavailable and every other capability is untouched. The switch is read from configuration at
process start, so **turning it takes a restart of the service, not a deploy**: the image, the
migrations and the contract do not move (`D-038`). A restart-based switch is the documented
mechanism; a runtime reload is not in the constitution and is not worth a config-watch thread
for a knob turned once a quarter.

## Turning one off

```
CATALYST_AI_CAPABILITY_SUMMARIZE__ENABLED=false   # in the deployment's environment
```
then restart the API and the worker. Check:

```
catalyst_ai_errors_total{code="ai.capability.disabled"}   # rises
catalyst_ai_provider_calls_total{capability="summarize"}  # stops
```

## Turning one back on

Remove the variable (the default is `true`) and restart. The switch leaves no state: cached
answers from before the switch are still served, which is why the cache TTL is the lag between
re-enabling and a capability looking normal again.

## What each capability degrades to

| Capability | The backend receives | What the member sees (the backend's choice) |
| --- | --- | --- |
| `improve-story`, `generate-children`, `propose-workflow`, `generate-tests`, `post-mortem`, `release-notes` | `ai.capability.disabled` | the assisted action is hidden or greyed |
| `summarize`, `translate`, `unfurl` | `ai.capability.disabled` | the raw text, no summary, no card |
| `search` | `ai.capability.disabled` | the backend's own keyword search, if it has one |
| `documents` (ask, generate, ingest) | `ai.capability.disabled` | no grounded answers; ingestion queues on the backend's side |
| `assistant` | `ai.capability.disabled` as the stream's terminal `error` frame | the assistant is unavailable; the thread is intact |

## When to use it

A provider outage confined to one capability, an eval regression with no pin available, a
runaway spend, or a security finding in one pipeline. Not for a load problem — that is what the
per-organisation concurrency bound and the queue are for.
