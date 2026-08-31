# Known limitations

These are intentional prototype scope boundaries, not defects. The prior
independent build+audit pass found **no defects** in `src/engine.py`'s
glossary, market-rules, or reviewer-workflow logic, and this release pass
did not change that logic's behavior for the approve/reject paths (it only
extended the workflow with a third, additive decision:
`revision_requested`).

## Scope limitations

- **No real authentication or authorization.** There is no login, no user
  accounts, and no access control. The native-reviewer panel is a UI-level
  role selector -- anyone running the app can act as the reviewer.
- **No persistent database.** Source content, glossary, and market rules
  are static local JSON files in `data/synthetic/`. The audit trail
  (`data/synthetic/audit_log.json`) is a local file written by the running
  process. In-progress drafts live only in Streamlit's `session_state` and
  are lost on browser refresh, app restart, or the in-app "Reset state"
  button.
- **No real translation, transcreation, terminology-management, or
  legal/compliance system integration.** See the Integration matrix in
  `README.md`. The only optional live call in this repo is the Claude
  draft-generation path in `src/llm.py`, gated by `MOCK_MODE`.
- **No reviewer notification or routing.** Approving, rejecting, or
  requesting revision all happen synchronously in the same app session --
  there is no email, ticketing, or queueing system routing drafts to an
  actual native-speaker reviewer.
- **Twelve source assets and six target markets, not an open catalog.**
  The seeded data is illustrative and fixed; adding a market or asset type
  requires editing the JSON files (see `docs/data-model.md`), not a
  self-serve admin UI.
- **Mock-mode translation is not a translation.** `MOCK_MODE=true`
  (default) produces a deterministic, clearly-labeled placeholder: brand
  glossary substitutions are applied correctly (the one piece of output
  that must be accurate for the demo to be meaningful), but every other
  sentence is tagged `(XX mock)` rather than actually translated. Live mode
  produces a real Claude-generated first-pass draft, but even that is
  explicitly a draft for human review, not a certified or legally-reviewed
  translation.
- **No multi-user or concurrent-session support.** This is a single-process
  Streamlit demo intended for one reviewer exploring the workflow at a
  time; concurrent writers to `audit_log.json` are not guarded against.

## Defects found during this release pass

None. The seeded-data expansion (3 -> 12 source assets, 3 -> 6 markets) and
the additive `revision_requested` review state were built and tested
against the existing, already-audited `src/engine.py` logic without
modifying its approve/reject behavior. All 34 tests pass; see
`docs/evaluation-plan.md` for what they check.
