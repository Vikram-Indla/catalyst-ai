# Budget exhaustion — `TenantBudgetExhausted`: an organisation hits its daily cap

**Alert:** `TenantBudgetExhausted`, one per organisation and capability: the alert's labels are
the tenant and the capability it is being refused on.

## What it means

Every call reserves its estimated cost against the organisation's daily cap before it reaches
the provider, and settles the real cost afterwards. Over the cap, the door refuses with
`ai.budget.exceeded` (429) and a `Retry-After` that points at the end of the day. A refused
tenant is never served a cheaper or slower answer — the cap is a promise about spend, not a
quality dial.

## The first three commands

1. `sum by (organization, capability) (increase(catalyst_ai_budget_refused_total[1d]))` — how
   many calls each tenant is losing, and on what; a handful at the end of the day is the cap
   working. Several organisations at once is the fleet, not a tenant.
2. `sum by (capability) (increase(catalyst_ai_provider_cost_micros_total{organization="<id>"}[1d]))`
   with the alert's organisation — where its spend went. A digest or an ingest of a large corpus
   is the usual answer.
3. `sum by (organization) (increase(catalyst_ai_provider_cost_micros_total[1d]))` — whether the
   tenant is an outlier or the default cap is simply too low for normal use.

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
