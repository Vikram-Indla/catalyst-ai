# Budget exhaustion — an organisation hits its daily cap

**Alert:** `TenantBudgetExhausted`.

## What it means

Every call reserves its estimated cost against the organisation's daily cap before it reaches
the provider, and settles the real cost afterwards. Over the cap, the door refuses with
`ai.budget.exceeded` (429) and a `Retry-After` that points at the end of the day. A refused
tenant is never served a cheaper or slower answer — the cap is a promise about spend, not a
quality dial.

## The first three commands

1. `sum by (organization) (increase(catalyst_ai_provider_cost_micros_total[1d]))` — who is
   spending, and whether it is one organisation or the whole fleet.
2. `sum by (capability) (increase(catalyst_ai_provider_tokens_total[1d]))` — which capability is
   the spend. A digest or an ingest of a large corpus is the usual answer.
3. `sum(increase(catalyst_ai_errors_total{code="ai.budget.exceeded"}[1d]))` — how many calls the
   tenant is actually losing; a handful at the end of the day is the cap working.

## What to do

- **Expected burn** (a big ingest, a migration): raise that organisation's cap for the day. The
  cap is `TENANT_BUDGET_DEFAULT_MICROS_PER_DAY`; a per-organisation override is a configuration
  change and a restart (`ARCH-008 §2`).
- **Unexpected burn**: look for a retry loop on the backend's side (the same request hash over
  and over — the cache would have served a repeat, so a miss storm means the key moved), or an
  organisation newly ingesting its whole wiki. The job queue's depth tells you which.
- **A runaway capability**: disable it for everyone (`kill-switch.md`) rather than let one
  tenant's loop spend the fleet's budget.

## When to page

A single tenant at its cap is a ticket. Every tenant at its cap on the same day is a page: that
is a pricing change, a model swap or a loop, and it costs money every minute.
