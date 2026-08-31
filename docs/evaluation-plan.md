# Evaluation plan

## What "correct" means for this agent

This agent's core logic is deterministic and rule-driven (not an LLM
judgment call in mock mode), so "correct" is defined precisely, per
component:

1. **Glossary compliance (`check_glossary_compliance`)**
   - A "do not translate" glossary term (e.g. `Northfield Cloud`) that
     appears in the source text must survive verbatim, case-insensitively,
     in the localized draft for every target language. If it doesn't,
     that's a violation.
   - A term with an "approved translation" rule (e.g. `Free Trial` ->
     `kostenlose Testversion` for German) must have that exact approved
     phrase present, case-insensitively, in the draft. If it's missing,
     that's a violation.
   - A glossary term that never appears in the source asset's body must be
     skipped entirely for that asset (no false-positive violations).
2. **Market-rule flags (`apply_market_flags`)**
   - `requires_legal_review` must be attached if and only if
     `market_rules.json[<lang>].requires_legal_review` is `true`.
   - `requires_cultural_review` must be attached if and only if
     `market_rules.json[<lang>].requires_cultural_review` is `true`.
   - An unconfigured/unknown language must return no flags, not raise.
3. **Reviewer workflow + audit log (`submit_for_review`,
   `record_review_decision`)**
   - Every submission, approval, rejection, and revision request must
     update `LocalizationDraft.review_status` to the correct value and
     append a correctly-shaped, correctly-ordered entry to the audit log
     (matching `from_status` / `to_status` / `action` / timestamp).
   - `record_review_decision` must reject any decision value other than
     `approved`, `rejected`, or `revision_requested`.
   - A draft with `rejected` or `revision_requested` status must be
     resubmittable back to `pending`.
4. **Seeded-data scale invariants**
   - Exactly 12 source assets, exactly 6 target markets, and glossary
     coverage for all 6 languages on every term -- these are structural
     guarantees the demo's metrics panel depends on, so they're tested
     directly against the JSON files, not just inline fixtures.
5. **Graceful degradation**
   - Requesting a target language that has no `market_rules.json` entry
     and no glossary rules (an "unconfigured" language) must not raise an
     exception anywhere in `build_localization_draft` -- it should come
     back as a valid, pending draft with empty flags and empty violations
     (nothing to check against), never a crash.

## How tests check it

`tests/test_engine.py` (12 tests) covers items 1-3 above against a small,
hand-written glossary/market-rules fixture, independent of the seeded JSON
files -- this is the original, already-audited core-logic test suite and it
was not modified.

`tests/test_expanded_markets.py` (22 tests) covers items 3-5 against the
*actual* seeded JSON files in `data/synthetic/`, specifically:

- Structural checks on the seeded data itself (asset count, market count,
  glossary language coverage).
- A single matrix test that runs `build_localization_draft` across all
  12 x 6 = 72 asset/language combinations and asserts none of them raise
  and all return well-formed drafts.
- Glossary-compliance violation and no-violation cases for each of the 3
  newly added languages (French, Brazilian Portuguese, Korean).
- Market-rule flag correctness for each of the 3 newly added languages,
  including one market (`ko`) that carries both flags simultaneously.
- Graceful-failure tests for an unconfigured target language, at the
  `apply_market_flags`, `check_glossary_compliance`, and full
  `build_localization_draft` levels.
- Revision-requested state tests: construction, a distinct audit-log
  transition from rejection, and the resubmit-after-revision-request loop.

Total: **34 tests**, run via `pytest -v`; see the exact command and passing
output referenced in `README.md`.

## Known evaluation gaps (by design, for a prototype)

- No automated check of *translation quality* -- mock-mode output is a
  labeled placeholder, not a real translation, so there is nothing
  linguistic to evaluate in mock mode. Live mode (`MOCK_MODE=false`) calls
  Claude for a first-pass draft, but its quality is judged by the human
  native-speaker reviewer in the app, not by an automated test.
- No load, concurrency, or performance testing -- this is a single-user,
  single-process Streamlit demo (see `docs/limitations.md`).
