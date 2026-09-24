# generate-children — eval set

**Set version:** 2 · **Cases:** 144 — `target:stories` 49, `target:epics` 41, `target:children` 54
(5 of them draft-only record children: key results under an objective and project objectives
under a card, English and Arabic, one repeating a sibling; `strata-` ids, `tools/evalsets_strata.py`)
(12 tagged `injection`, 6 tagged `leakage`) · **Provenance:** synthetic parents (epics, initiatives,
features) authored from the behaviour of the previous system's `ai-generate-stories`,
`ai-generate-epics` and `ai-suggest-children` and from where they went wrong: children of the wrong
level, repeats of existing siblings, stories without acceptance criteria. No case comes from tenant data.

## What a good output is

- Every candidate is exactly the child level: the parent's next level in the supplied hierarchy,
  or the `child_level` the request names. One wrong level refuses the whole response
  (`ai.output.invalid`, detail `hierarchy_violation`) — that path is proven by unit and contract
  tests on scripted bad outputs, so the set's `level_correct` floor is 1.0.
- A candidate that repeats a supplied sibling carries `duplicate_of` naming it and does not count
  as new; new candidates do not repeat each other (`duplicates_marked`, `no_duplicate_candidates`).
- Story-level candidates carry acceptance criteria (`criteria_present`).
- The count of new candidates respects `max_items` and the case's minimum; an empty result carries
  its reason (`parent_too_vague`, `siblings_cover_it`) and a non-empty one carries none.
- The parent's script is preserved; no identifier is invented; no fence echoed, no foreign key,
  link or secret; none of the case's forbidden terms.

- **draft-only**: every candidate is marked a draft, carries no acceptance criteria, states no
  number, date or link the parent and the sources lack, and writes Latin digits (`drafts_only`,
  floor 1.0); a candidate that states one is withheld by the pipeline and counted in `withheld`.

## Graders

All deterministic (`graders.py`); the shared quality signals come from `improve-story`'s
`quality` module and `platform/similarity`. Floors in `thresholds.yaml`; the level, duplication,
language, identifier and safety floors are 1.0 because one miss is a defect.

## Fixtures

Authored, as for `improve-story` v1 (see that README): `tools/record.py --authored` writes them
under the request hashes; the first `make record LIVE=1 CAP=generate-children` replaces them and
the numbers in `docs/04-ledgers/eval-sets.md` are re-stated.
