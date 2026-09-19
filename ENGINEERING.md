# Catalyst One AI service — read this first

The Python service behind every assisted feature of Catalyst One: story improvement, structured
generation, retrieval, summaries, translations, document intelligence, the assistant. It is a
**dependency of the Go backend behind one versioned OpenAPI contract**. It holds no business rule,
owns no product fact, reads no product table: it receives classified inputs, returns a schema-valid
result with provenance, and the backend decides what the result means.

This file is the bootstrap for every contributor and every tool. It is short on purpose: it tells
you where the law is and how a session runs. It does not repeat the law.

## Precedence

When instructions conflict, the higher one wins. If two at the same level conflict, stop and ask.

1. An explicit instruction from the lead, recorded in `brain/02-DECISIONS.md` as `D-NNN`.
2. `docs/02-rules/` — the rules (`RULE-000` first). Binding, CI-enforced.
3. `docs/03-adr/` — architecture decisions. Locked unless superseded by a newer ADR.
4. `docs/01-architecture/` — how the service is shaped. Follow it; propose changes as an ADR.
5. The code. Where code and docs disagree, file `F-NNN` in `brain/03-FINDINGS.md`; never pick silently.

## Every session, in order

1. Read `brain/01-STATUS.md`, then the ticket you are on (`AI-NNN`).
2. Read the minimum relevant context: the rule and architecture pages the ticket names, the files
   you will change, the golden capability where a pattern already exists, and — when the ticket
   retires a function of the previous system — that function, for its **behaviour**, never its code.
3. Write the impact matrix (`RULE-007 §1`) into the session record before any edit. A row you
   cannot fill is a `Q-NNN`, not a guess. An eval set that does not exist is the first thing you build.
4. Work inside the capability or package the ticket names. Anything noticed outside it is an
   `F-NNN` or a `Q-NNN`, not a fix.
5. Run `make verify` and `make ci` before claiming anything is done. Paste both. "Should work" is not done.
6. Write the session record in `brain/sessions/<YYYY-MM>/NNN-<slug>.md` from the template, with
   the eval score, the p95 latency and the p95 cost when a capability was touched.
7. Git is hybrid (`RULE-005`): list the files, propose one Conventional Commit line, and **ask**.
   Commit only after an explicit yes in chat. Never push `main`. Never force.

## Where things are

```
src/catalyst_ai/
  contract/        the request, response and error models mirrored in api/openapi.yaml — a leaf
  config/          the one typed settings object; the only reader of the environment
  platform/        the shared kernel — errors, logging, tracing, budgets, cache, tenancy, clock, ids
  providers/       the Provider port and one adapter per provider; the only code that calls a model
  retrieval/       embeddings, chunking, the per-tenant index over the service's own database
  capabilities/<name>/   one capability: pipeline, prompt files, schema, post-processing
  app.py           the FastAPI composition root
api/openapi.yaml   the contract, generated from the models and committed; CI fails on drift
evals/<name>/      the versioned eval set, its graders and thresholds, beside the capability
tests/             unit beside the layer it mirrors · architecture/ · contract/ · fixtures/
tools/checks/      every gate, in Python, run by make verify; selftest plants a violation per check
docs/              durable: 01-architecture · 02-rules · 03-adr · 04-ledgers · 05-threat-models · 06-runbooks · 07-GLOSSARY
brain/             working memory: 01-STATUS · 02-DECISIONS · 03-FINDINGS · 04-OPEN-QUESTIONS · sessions/
```

## Hard lines — the ten invariants (the full list is `RULE-000 §3`)

1. **The boundary is the product.** Called only by the backend through the contract; reads no
   product table; every input carries `organization_id` and a data class; `RESTRICTED` is refused
   at the door; the service's own rows are per tenant with RLS; no tenant data trains anything;
   provider retention is refused in configuration. A module importing a product schema: CI red.
2. **Contract first.** Every operation has pydantic request and response models mirrored in
   `api/openapi.yaml`, its error codes, `capability_version`, `prompt_version`, `model` provenance
   and a documented degradation. A raw dict crossing a boundary: CI red.
3. **Eval before prompt.** Every capability has a versioned eval set with thresholds beside it;
   the gate fails below them; a prompt is a versioned file with a header. A prompt string in code: CI red.
4. **No network in the suite.** Provider calls in tests are recorded fixtures; a socket opened by
   a test fails the run; a re-recording states its reason in the session record.
5. **Providers behind one port.** One `Provider` port; adapters own retries, timeouts, circuit
   breaking and cost accounting. A model name outside the register or configuration: CI red.
6. **Code quality, tightened.** Python 3.12 pinned to the image; `uv` with a lock; `ruff` with the
   full group list and `ANN401` on; `mypy --strict`; file ≤ 300 logical lines, function ≤ 50 lines,
   complexity ≤ 10, parameters ≤ 5, branches ≤ 10; banned filename stems; one capability per
   package; one typed settings object; no global mutable state; no notebook; no "why" comment.
7. **DRY as a check.** Rule of two inside a capability; across capabilities only through a named
   package under `platform/` or `retrieval/`, never a `utils`. Duplicate blocks: CI red.
8. **Budgets are tests.** Every capability declares p95 latency and p95 cost; a change that crosses
   either fails the gate; per-tenant budgets are enforced in the service, not assumed of the caller.
9. **Observability without content.** Every provider call logs organisation, capability, versions,
   model, tokens, cost, latency, cache hit and outcome — never the prompt or the completion. A
   content field in a logging call: CI red.
10. **Zero tolerance, parity, hooks.** `make verify` is the gate and equals CI; `make ci` runs the
    workflow verbatim in the CI image before any push; `.githooks` refuse red on commit and push;
    no `noqa` or `type: ignore` without an allowlisted reason; coverage tiered — policy and safety
    100%, pipelines 95%, adapters 80%, overall 90%. Nothing merges red.

The gate is the meanest reviewer on this team and the fairest. The model is an untrusted input
generator; everything around it — the contract, the schema, the eval set, the budget, the
boundary — is the product.
