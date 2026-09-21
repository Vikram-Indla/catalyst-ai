# Threat models

One per capability family (`ARCH-001 §3`) and one for the platform (token, storage, jobs,
retention), from `THREAT-000-template.md`, reviewed against OWASP ASVS 5.0 and the OWASP LLM top
ten before the family's first capability reaches production. A `built` capability whose family
has no `Reviewed` threat model is a finding.

| ID | Family | Status |
| --- | --- | --- |
| THREAT-001 | platform — token, storage, jobs, retention | with the scaffold |
| THREAT-002 | rewrite | Draft — `THREAT-002-rewrite.md`, with `improve-story` v1 |
| THREAT-003 | structured generation | Draft — `THREAT-003-structured-generation.md`, with `generate-children` v1 |
| THREAT-004 | summaries and translation | Draft — `THREAT-004-summaries.md`, with `summarize` and `translate` v1 |
| THREAT-005 | retrieval and knowledge | Draft — `THREAT-005-retrieval.md`, with `search` v1 |
| THREAT-006 | assistant | with `assistant-chat` |
