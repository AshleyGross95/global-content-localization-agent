# Workflow

Step-by-step user flow through `app.py`, matching the four numbered sections
of the running app in order.

## 1. Generate localized drafts

1. The user picks one **source asset** from the 12 seeded fictional assets
   (`data/synthetic/source_content.json`) via the `Source asset` selectbox.
   The English source text is shown, read-only, for reference.
2. The user picks one or more **target languages** from the 6 seeded markets
   (`data/synthetic/market_rules.json`) via the `Target language(s)`
   multiselect (all 6 selected by default). For each selected language, the
   market's `formality_note` is shown immediately, before generating
   anything, so the reviewer knows what register to expect.
3. Clicking **"Generate localized draft(s)"** calls
   `build_localization_draft(source_asset, lang, glossary, market_rules)`
   for each selected language. That function:
   - Produces the draft text via `src/llm.py` (deterministic mock
     placeholder by default, or a live Claude call if `MOCK_MODE=false`).
   - Runs `check_glossary_compliance` against the brand glossary for that
     language.
   - Runs `apply_market_flags` against that language's market rules.
   Each resulting `LocalizationDraft` is immediately submitted for review
   (`submit_for_review`, status becomes `pending`) and stored in
   `st.session_state.drafts`, keyed by `(source_id, target_language)`.

## 2. Draft results

For the currently selected source asset, every generated draft is shown in
its own bordered panel: the localized draft text, a three-metric row
(review status, glossary-violation count, flag count), the specific
glossary violation strings (if any), and the specific market-rule flags with
their fictional reasons (if any). An explicit info box above this section
states that these drafts do not replace legal, regulatory, or local-market
review -- see `docs/limitations.md` and the in-app disclaimer text itself.

## 3. Native reviewer panel

The user plays the native-speaker reviewer role for every draft still
`pending`:

- **Approve** -- `record_review_decision(draft, REVIEW_APPROVED, notes)`.
  Status becomes `approved`; an audit-log entry is appended.
- **Request revision** -- `record_review_decision(draft, REVIEW_REVISION_REQUESTED, notes)`.
  Status becomes `revision_requested` -- a distinct state from rejection,
  meant for "close, but needs specific changes" rather than a hard no.
- **Reject** -- `record_review_decision(draft, REVIEW_REJECTED, notes)`.
  Status becomes `rejected`.

Every decision requires the reviewer-notes text area to be visible (notes
are optional for approval, but strongly expected in practice for a
rejection or revision request, matching real localization QA workflows).

Reviewed drafts (`approved`, `rejected`, or `revision_requested`) move to a
"Reviewed drafts" list below the pending queue. A `rejected` or
`revision_requested` draft can be **resubmitted for review**
(`submit_for_review`), which moves it back to `pending` and appends another
`submitted` audit-log entry -- modeling the real-world "revise and
resubmit" loop shown in the architecture diagram.

## 4. Audit trail

Every `submitted` / `approved` / `rejected` / `revision_requested`
transition, across every draft generated in the current server process, is
persisted (append-only) to `data/synthetic/audit_log.json` and rendered as
a table. This is the full, timestamped history of who decided what, when --
the audit trail a real localization-ops team would need to answer "why was
this German draft approved on this date."

The in-app **"Reset state"** button clears both `st.session_state.drafts`
(in-memory drafts) and truncates `audit_log.json` back to `[]`, returning
the demo to its canonical empty starting state.
