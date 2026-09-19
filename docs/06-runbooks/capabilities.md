# Capabilities — one line each

What to check when quality drops, how to disable without a deploy, what the backend receives.

| Capability | Quality drops: check | Disable | The backend receives when off |
| --- | --- | --- | --- |
| `improve-story` | `make evals --set improve-story` against the fixtures (a red grader names the property); `docs/04-ledgers/eval-sets.md` for the last live numbers; the provider status page and `provider_calls` outcomes per model; `MODEL_TEXT_DEFAULT` for an unplanned model move | `CATALYST_AI_CAPABILITY_IMPROVE_STORY__ENABLED=false` | `503` with `ai.capability.disabled` before any provider call; the backend shows the feature as unavailable and keeps the original text |
| `generate-children` | `make evals --set generate-children` (a red `level_correct` means the model drifted on levels — the pipeline refuses such responses, so users see `ai.output.invalid`, not wrong items; a red `duplicates_marked` means the lexical threshold in `platform/similarity` needs the retrieval-backed path); the provider status and `provider_calls` outcomes | `CATALYST_AI_CAPABILITY_GENERATE_CHILDREN__ENABLED=false` | `503` with `ai.capability.disabled` before any provider call; the backend hides the breakdown action |
