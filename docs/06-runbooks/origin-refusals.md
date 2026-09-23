# Refused origins — `OriginRefusalsHigh`, `OriginForged`: the door is turning callers away

**Alerts:** `OriginRefusalsHigh` (a steady rate), `OriginForged` (a signature that is not the
backend's — page immediately).

## What it means

Every request carries an envelope the backend signed; the door verifies it before any route and
refuses with `401 auth.origin.invalid` and no detail. The reason lives in the security log and in
`catalyst_ai_origin_refused_total{reason}` — that counter is the whole diagnosis.

## The first three commands

1. `sum by (reason) (rate(catalyst_ai_origin_refused_total[15m]))` — the reason is the answer:

| Reason | What it means | Do |
| --- | --- | --- |
| `bad_signature` | a forged envelope under a known key id | **page**; rotate the key (`key-rotation.md`, emergency) |
| `unknown_key` | a rotation out of order, or a retired key still in use | `key-rotation.md`: is the old key still listed? |
| `expired`, `not_yet_valid`, `too_long_lived` | clock drift, or the backend signing at enqueue time instead of send time | compare the two clocks; `AUTH_CLOCK_SKEW_SECONDS` is the tolerance |
| `replayed` | a retry re-sent the same envelope (a backend defect), or a real replay | the backend signs every attempt afresh; if it does, treat as an attack |
| `body_mismatch` | a proxy rewriting bodies, or a hash over a different serialisation than was sent | compare the bytes; `bh` is over the bytes exactly as sent |
| `organization_mismatch`, `capability_mismatch` | the backend signed for one thing and sent another | a backend defect; correlate by `X-Request-Id` in its log |
| `missing`, `malformed` | something that is not the backend is calling — a scanner, an old client | find the source in the ingress log; the service is unaffected |
| `no_job_window` | a job submission without `job_exp` | the backend's poller; the changelog entry says what to sign |
| `unverifiable` | the replay store did not answer — the door failed closed | `replay-store-down.md` |

2. `sum(rate(catalyst_ai_http_requests_total[15m]))` — is anything getting through? A refusal
   rate with no served traffic is a rotation or a clock, not an attacker.
3. The ingress log for the source address of the refused calls: one address that is not the
   backend is a scanner and needs nothing from this service.

## When to page

Any `bad_signature`. A `replayed` or `body_mismatch` rate the backend cannot explain within the
hour. A refusal rate that covers *all* traffic — that is an outage of the product, not a security
event, and usually a rotation that reached one side only.

## What never helps

Loosening the window or the skew to make refusals stop. Both are bounded in configuration
(`0..60`), and a refusal is the door doing its job; the fix is on the side that signs.
