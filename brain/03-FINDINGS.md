# 03 — Findings

`F-NNN` — where · observed · expected · proposal · state. Code-versus-docs disagreements, a wrong
grader, and out-of-scope defects go here, never into the change.

| ID | Date | Where | Observed | Expected | Proposal | State |
| --- | --- | --- | --- | --- | --- | --- |
| F-001 | 2026-09-18 | the previous system's `chat-unfurl`, `kb-feedback`, `kb-cleanup`, `ai-theme-prewarm`, `catyflow-*` | No model call in these functions; they are link previews, feedback storage, cache purging, cache warming and token handling | Every function under the migration's assisted list maps to a capability or is explicitly retired without one | Recorded in `docs/04-ledgers/capabilities.md` as retired without a capability; the backend confirms it owns them | open |
| F-002 | 2026-09-18 | `pyproject.toml` first lock | `pydantic-settings` 2.12.0, `pytest` 9.0.2, `starlette` 0.50.0 carried known vulnerabilities | zero known vulnerabilities in the lock | bumped to 2.14.2, 9.0.3, 1.3.1 (FastAPI 0.141.1) before the first green | closed (session 002) |
| F-003 | 2026-09-18 | `platform/logging/setup.py` | the redacting filter redacted the logger's own `name` attribute | only extra attributes with content keys are redacted | skip standard attributes; test added | closed (session 002) |
| F-004 | 2026-09-18 | the previous `ai-improve-story` | it sent attachment URLs to the provider and read comments from product tables | inputs arrive classified in the request; attachments as extracted text when the product wants them | `Q-003`; v1 carries neither | open |
