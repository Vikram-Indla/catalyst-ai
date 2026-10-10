# 059 — The hosted release job is skipped, never red, until a deploy target exists

**Date:** 2026-09-25 · **Ticket:** AI-046 · **Capability or package:** `.github/workflows/release.yml`, `tools/checks/release_job.py`, `tools/rules.py` (`RELEASE_GUARD`), `RULE-006` · **Author:** a contributor

The release workflow (record 048) runs on every push to `main`. It failed on `b80296f` in 12 s:
the repository has no release variables, because the cloud project does not exist yet. A red run
on `main` that everyone expects teaches everyone to ignore red. The job is now guarded: until the
repository's `RELEASE_REGISTRY` variable names a deploy target, the job is skipped, not failed.

## Read
- GitHub Actions evaluates a job-level `if:` before the job starts, and a job whose condition is
  false is reported as skipped. The `vars` context (repository variables) is available there.
- The guard is keyed to the deploy target alone. With a registry set but the login's variables
  missing, the job still runs, and `tools/release.py` refuses by name. A half-configured target is
  a loud error, not a silent skip.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-046
Capability:      none — the hosted release workflow
Inputs:          the repository's RELEASE_REGISTRY variable (read by the guard)
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    no deploy target → the job is skipped; a half-configured target still refuses
Cache:           none
Safety:          unchanged; the job still holds id-token alone and stays print-only
Contract:        unchanged
Invariants:      unchanged
Blast radius:    LOCAL — one workflow and its check
Decision level:  1
ADR:             none
```

## What changed
- **`release.yml`**: the job carries `if: ${{ vars.RELEASE_REGISTRY != '' }}`.
- **The workflow check** (`release_job`, walked by `tools/checks/ci`) requires exactly that guard:
  a job without it, or with another condition, is refused. `RULE-006`'s row says so.

## Red first
```
the guard not required by the check
  test_the_job_is_skipped_until_a_deploy_target_exists_and_the_guard_is_required   FAILED
  (and the committed workflow, now carrying `if:`, refused as an unknown key)   2 failed
restored: test_release_job 5 passed; the ci check green; selftest 58/58
```

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks: lint, types, the tests above, the ci check and the selftest green. The full gate, on
the tree this change is committed from:
```
$ make verify
(pending: pasted from the run)
$ make ci
(pending: pasted from the run)
```

## Decisions and questions
- The skipped job shows no message; GitHub's skip is the message. When staging exists, setting the
  repository's variables turns the job on, still print-only until the lead approves the hosted
  login (record 048).

## Commit
- `ci(release): skip the release job until a deploy target exists`
