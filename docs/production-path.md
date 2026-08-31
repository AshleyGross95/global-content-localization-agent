# Production path: prototype -> pilot -> production

Expanded version of the README's Roadmap section, one stage at a time.

## Prototype (this repo, current state)

- Deterministic glossary compliance checking and data-driven market-rule
  flagging (`src/engine.py`), backed entirely by synthetic JSON seed files.
- Mock-by-default translation drafts (`src/llm.py`), with an optional live
  Claude call gated by `MOCK_MODE` and `ANTHROPIC_API_KEY`.
- In-session native-reviewer workflow with three distinct outcomes
  (approve / reject / request revision) and a persistent, timestamped,
  append-only audit trail (`data/synthetic/audit_log.json`).
- 12 fictional source assets across varied content types, 6 target markets,
  34 automated tests.
- No auth, no database, no real integrations -- single-process Streamlit
  app, single reviewer at a time.

## Pilot

- **Real terminology management**: replace `glossary.json` with a live
  connection to an actual TMS (e.g. a terminology database or translation
  memory system), so glossary rules are maintained by localization ops, not
  hand-edited JSON.
- **Real market/compliance rules source**: replace `market_rules.json` with
  a connection to whatever system of record legal/compliance already uses
  for market-specific requirements (even a shared spreadsheet with an API
  would be a real improvement over a static file).
- **Reviewer routing**: route drafts needing `requires_legal_review` or
  `requires_cultural_review` to the actual responsible reviewer via email
  or a ticketing system, instead of a synchronous in-app panel.
- **Persistent storage**: move source content, drafts, and the audit log
  from local JSON files to a real database, so drafts survive restarts and
  multiple reviewers can work concurrently without clobbering each other.
- **Pilot-scale content**: expand beyond the 12 seeded asset types to a
  pilot team's actual content categories, and beyond 6 markets to the
  team's actual target-market list.

## Production controls

- **Role-based access control**: real authentication, with distinct
  permissions for content requesters, native reviewers, and legal/cultural
  reviewers -- no more UI-level role selection.
- **Mandatory legal sign-off gating**: a draft flagged
  `requires_legal_review` should be blocked from any "ready to publish"
  state until an actual legal reviewer (not just a native-speaker QA
  reviewer) has recorded approval -- today the flag is informational, not
  a hard gate.
- **Versioned glossary and market-rule changes**: track who changed a
  glossary term's approved translation or a market's review requirements
  and when, with an approval step for changes to either.
- **Full auditability**: extend the existing audit-log pattern (already
  append-only and timestamped) with reviewer identity, IP/session
  metadata, and immutability guarantees appropriate for a compliance
  audit trail, not just a demo history table.
- **SLAs and escalation**: time-to-review targets per market/flag
  combination, with automatic escalation for drafts stuck in `pending` or
  `revision_requested` past a threshold.

## Rollout & adoption measurement

- **Glossary-violation rate over time**, by market and by asset type --
  is the mock/live draft step getting brand terms right more often as the
  glossary matures?
- **Average time-to-approval per market** -- which markets' review
  requirements (legal, cultural, or both) create the longest bottlenecks?
- **Revision-request rate and reasons** -- distinct from rejection rate,
  this measures how often a draft is "close" versus fundamentally wrong,
  and what specifically reviewers ask to change.
- **Which asset types or markets need more upfront translation-memory /
  glossary coverage**, based on where violations and revision requests
  concentrate.
