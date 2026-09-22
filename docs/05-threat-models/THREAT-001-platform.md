---
id: THREAT-001
family: the platform — the proof of origin, the replay store, the job gate, the keys
status: Draft
reviewed: —
asvs: 5.0
llm-top10: 2025
---

# THREAT-001 — the platform: who may make this service work

## Assets

The right to call any capability for any organisation (`RESTRICTED` in effect: it is every
tenant's data at once); the backend's private key (`RESTRICTED`, never on this side); the
service's public keys (`INTERNAL`); the replay store (platform state); a job row and its payload
(the payload's own class); the security log (ids and reasons only).

## Entry points and trust boundaries

Every operation under `/v1/` (the health routes are exempt); the `jobs` table when it exists;
the configuration. Trust changes at the origin middleware, which runs before any route: it reads
the body once, decodes the envelope, verifies the signature with the public key `kid` names,
checks issuer, audience, window and skew, honours the nonce once, binds the body hash, the
organisation the body names and the capability the route declares, and only then hands the
same bytes on. A job's proof is verified again by the worker before executing.

## Attackers

Anyone holding the old static bearer (there is none left) · anyone with write access to the
service's database (a leaked credential, an injection elsewhere, a misconfigured role) · anyone
on the network between the backend and the service (a replayed request, a swapped envelope) ·
a backend bug (a stale clock, a wrong `org`, an envelope reused across calls) · anyone who
obtains configuration on this side (a public key is all there is) · anyone reading logs.

## Threats

| # | Attacker | Entry point | Attack | Mitigation (code) | Verified by | ASVS / LLM |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | holder of a stolen bearer | any operation | present `Authorization: Bearer <token>` | there is no token: the scheme is the signed envelope, a bearer is `malformed` → `401`; no code path reads a bearer (`tools/checks/origin`) | `test_the_old_bearer_and_a_missing_header_are_refused_alike`; the check red on its plant | V3.1 |
| 2 | database writer | the `jobs` table | insert a row claiming an organisation and a capability | a row carries the API's verified envelope and its payload hash; `verify_stored` refuses a missing or made-up envelope, a swapped organisation or capability, an edited payload, a closed job window → `quarantined`, never run (`INV-054`) | `test_the_attackers_rows_are_quarantined`, `test_a_forged_signature_under_a_known_key_id_is_quarantined` | V4.1 |
| 3 | network | any operation | replay a captured request within its window | `jti` remembered until `exp` plus the skew in the replay store (`auth_nonces`, platform state); the second presentation is `replayed` → `401` | `test_a_replayed_envelope_is_refused_the_second_time`, `test_a_nonce_is_honoured_once_within_its_window`, the storage test | V3.2 |
| 4 | network, backend bug | any operation | a valid envelope for organisation A on a body naming organisation B | `bh` binds the exact bytes; a re-signed body under A's envelope fails `org` equals `organization_id` → `401` without saying which | `test_an_envelope_swapped_onto_another_organisation_is_refused`, `test_organisation_mismatch_is_refused_without_detail_and_logged_with_it` | V4.2 |
| 5 | network | any operation | edit the payload after signing | `bh` mismatch → `401` | `test_a_payload_edited_after_signing_is_refused`, `test_expired_unknown_key_and_edited_payload_are_refused` | V3.5 |
| 6 | network | any operation | move an envelope from `summarize` to `documents.generate` | `cap` equals the route's declared capability; an unknown path binds to nothing → `401` (no enumeration by status) | `test_each_claim_is_checked[capability]`, `test_unknown_route_is_refused_like_everything_else` | V4.1 |
| 7 | backend bug, network | any operation | an envelope minted far ahead, or long-lived, to be replayed later | `exp - iat` ≤ `AUTH_MAX_TTL_SECONDS` (60); `iat` in the future beyond the skew is `not_yet_valid`; the skew is bounded in configuration (0..60) | `test_each_claim_is_checked[too long lived, not yet valid, expired]`, `test_clock_skew_is_tolerated_but_no_more`, `test_origin_tolerances_are_bounded` | V3.3 |
| 8 | holder of this side's configuration | the keys | forge with what the service holds | the service holds public keys only; no signing primitive, no key generation, no cryptography import outside the registry (`tools/checks/origin`, `INV-053`) | the check red on its plant; `test_a_signature_by_an_unconfigured_key_under_a_known_id_is_refused` | V6.2 |
| 9 | anyone | rotation | keep using a retired key | two keys at most, by `kid`; a retired key is `unknown_key` → `401`; the rotation runbook removes the old key after the longest job window | `test_rotation_two_keys_verify_and_a_retired_one_refuses` | V6.4 |
| 10 | the database | the replay store | an outage that would let a replay through | fail closed: `unverifiable` → `503` with `Retry-After`; nothing is served until the nonce is proven once | `test_a_replay_store_outage_is_a_retryable_refusal_not_a_verdict`, `test_a_replay_store_outage_proves_nothing` | V3.2 |
| 11 | anyone | the refusal | learn which check failed | every refusal is `auth.origin.invalid` with one fixed message and no detail; the reason goes to the security log and the counter (`origin_refused{reason}`) | `_refused` in `test_origin.py`; `security_event` | V7.4 |
| 12 | anyone | logs | a claim's text, a body, a key in a log line | the security event carries ids and the reason only (`Where`); `tools/checks/logs` | the gate | LLM02 |

## Residual risk

- The job half is born verified but not yet exercised by a worker: the job model (`ADR-007`)
  has no table today. `verify_stored` and the `quarantined` state are the contract the table
  will be built to; the "real worker loop" proof lands with it.
- The replay store shares the service's database; a database write attacker can delete a nonce
  and replay once within the window. That attacker still cannot forge an envelope (threat 2),
  so the blast radius is one repeated legitimate request.
- The clock is the system's on both sides; the tolerance is five seconds by default. A machine
  whose clock drifts further refuses everything loudly rather than quietly.
- Accepted by: pending the lead (`D-035`, `D-036`).
