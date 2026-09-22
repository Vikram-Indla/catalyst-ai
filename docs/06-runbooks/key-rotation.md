# Key rotation — the backend's signing key, the service's public keys

The backend signs every request with an Ed25519 private key it alone holds; the service verifies
with the matching public key, named by `kid`, from `CATALYST_AI_AUTH_PUBLIC_KEYS`. Two keys may be
active at once, which is what makes a rotation a sequence with no refused call in it.

## When

On a schedule the operator sets (a quarter is reasonable), on any suspicion the private key
left the backend's runtime, and when a person who could read it leaves.

## The sequence

1. **The backend generates the new pair** (`crypto/ed25519`, the standard library) and keeps the
   private key in its own runtime configuration only. It hands over the public key as
   `<new kid>:<base64url of the 32 raw bytes>`. The service never sees a private key.
2. **Add the new public key to the service first.** `CATALYST_AI_AUTH_PUBLIC_KEYS` becomes
   `<old kid>:<old key>,<new kid>:<new key>`; restart the service (`catalyst-ai check` refuses to
   start unless both entries parse). Every request still verifies: the backend is still signing
   with the old key, which is still listed.
3. **Switch the backend to the new key** (`kid` in its envelopes changes). Watch
   `origin_refused{reason="unknown_key"}`: it must stay at zero. A rise means step 2 did not
   reach every instance of the service.
4. **Wait the longest job window.** A queued job carries the envelope it was accepted with; its
   worker verifies that envelope again before running, so the old key must stay listed until no
   job signed with it can still start (`job_exp` of the longest capability's budget window; a
   day is generous).
5. **Remove the old key.** `CATALYST_AI_AUTH_PUBLIC_KEYS` becomes `<new kid>:<new key>`; restart.
   A request still signed with the old key is now `unknown_key` → `401`, which is the point.

## Emergency (the private key is suspected leaked)

Steps 1–3 at once, then step 5 without waiting: a job signed with the leaked key is quarantined
by its worker rather than run (`docs/06-runbooks/job-quarantine.md`), and the backend resubmits it
under the new key. A short window of `401`s is the price of certainty.

## What to check

- `catalyst-ai check` after each configuration change: the keys load.
- `origin_refused` by reason, before and after each step; `unknown_key` and `bad_signature`
  stay at zero in a planned rotation.
- The security log names the `kid` of nothing — a refusal carries the reason and the request id
  only; correlate with the backend's own log by request id.

## What never happens

- A private key in this repository, in the service's configuration, in a fixture or in a log.
  `tools/checks/origin` refuses a signing primitive in the tree; the development pair used by
  the suite is derived from a fixed public seed and signs nothing in production.
- A shared secret between the two sides. A leak on the service's side forges nothing.
