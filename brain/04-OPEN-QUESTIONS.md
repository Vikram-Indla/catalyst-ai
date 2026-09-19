# 04 — Open questions

`Q-NNN` — question · why it blocks · options · the answer becomes a `D-NNN`. Every product
question a prompt would otherwise answer lands here.

| ID | Date | Question | Why it blocks | Options | State |
| --- | --- | --- | --- | --- | --- |
| Q-001 | 2026-09-18 | How do summaries, digests and standups refer to people? The previous system printed names from the profiles table; names are `RESTRICTED` and never enter this service. | Shapes the request models of `summarize-comments`, `summarize-standup`, `summarize-chat`, `digest`, `post-mortem`. | (a) the backend sends opaque labels (`participant_1`) and re-maps them in the UI; (b) the backend sends product handles it classifies `INTERNAL`; (c) summaries name nobody. Recommended: (a). | open |
| Q-002 | 2026-09-18 | Is any organisation opted in to quality sampling of `(input, output)` pairs, with what fraction and retention? | Shapes `QUALITY_SAMPLING_ORGANIZATIONS` and the retention job. | Default: none; each opt-in is a `D-NNN`. | open |
| Q-003 | 2026-09-18 | Attachments: the previous `ai-improve-story` and `ai-generate-*` read attachment URLs and images. Does the product want attachment text in these capabilities, and if so does the backend extract it before sending? | Shapes `source_texts[]` on the generation requests and whether `improve-story` v1 carries any. | (a) v1 without attachments; the backend adds `source_texts[]` (extracted, classified) in a later version; (b) `knowledge-ingest` first, then generation retrieves. Recommended: (a). | open |
| Q-004 | 2026-09-18 | What is the output language and tone by default? The previous prompt hard-coded English and a tenant-specific persona. v1 preserves the input's language unless `language` names a target and carries no persona. | Shapes the `language` default the backend sends and whether a persona field exists. | (a) preserve the input's language, no persona (v1's behaviour); (b) the organisation's configured language; (c) always English. Recommended: (a) with (b) as a backend-side default. | open |
| Q-005 | 2026-09-18 | Is the seven-level hierarchy fixed for every organisation, or may levels be disabled (`feature`)? | Shapes what the backend sends as `hierarchy[]` and whether stories under an epic are ever one call. | (a) fixed; (b) per organisation, sent as data (v1 supports both). | open |
