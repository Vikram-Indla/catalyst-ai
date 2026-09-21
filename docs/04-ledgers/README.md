# Ledgers

Registers of what exists. Five are **generated** by `make ledgers` from the descriptors, the
error module, the settings class, the register and the eval runs — never edited by hand; CI
fails on drift. Three are written by hand.

| File | Source | Content |
| --- | --- | --- |
| `capabilities.md` | Descriptors (`capabilities/*/descriptor.py`) | Capability, version, state, the previous system's functions it retires, inputs with data class, output, eval set, budget, model alias, kill-switch key |
| `errors.md` | `contract/errors.py` + descriptors | Error code, HTTP status, degradation, operations that can return it |
| `config.md` | `config/settings.py` | Variable, type, required, default, validation, data class, description |
| `providers.md` | `providers/*/models.py` + configuration | Alias → provider, concrete model id, context limit, price row, retention setting, date measured |
| `eval-sets.md` | `evals/*/README.md` + `eval_runs` | Per capability: set version, prompt version, model alias, scores per grader, p95 latency, p95 cost, date, session record |
| `invariants.md` | **By hand**, checked | `INV-NNN` — the registry: invariant, owner, enforcement, criticality, source; every enforcement must name an existing check (`tools/checks/invariants`) |
| `contracts-changelog.md` | **By hand** | Every contract change, with what the backend must do now |
| `parsers.md` | **By hand**, with the descriptor of `documents` | Per format: the library, why it beats the standard library, the limits and their reason classes, what is not parsed |
| `retirement.md` | **By hand** | Per previous function: `live` / `shadow` / `retired`, date, the capability, the eval run that justified it — created with the first `built` capability |

Until `make ledgers` exists, the generated files are written by hand from their sources in the
same change as the source; a drift between a ledger and its source is a finding.
