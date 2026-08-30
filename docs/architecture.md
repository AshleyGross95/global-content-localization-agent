# Architecture

```mermaid
flowchart LR
    A["Source Content\n(data/synthetic/source_content.json)"] --> B["Translation Layer\n(src/llm.py)\nMock placeholder or live Claude call"]
    B --> C["Glossary + Market-Rules Validation\n(src/engine.py)"]
    C --> D["Flagged Localization Draft\n(LocalizationDraft, src/models.py)"]
    D --> E["Native Reviewer Approval Workflow\napprove / reject + notes"]
    E -->|approved| F["Audit Trail\n(data/synthetic/audit_log.json)"]
    E -->|rejected: revise and resubmit| B
    E --> F
```

## Components

- **Source content (`data/synthetic/source_content.json`)** -- 2-3 fictional
  marketing assets (a product email, a landing page snippet, a renewal
  notice) in English, each with an id and body text. All names, brands, and
  copy are synthetic and fictional.

- **Translation layer (`src/llm.py`)** -- produces the first-pass localized
  draft text for a source asset + target language.
  - In `MOCK_MODE=true` (default), this is a deterministic, rule-based
    placeholder transform: brand-glossary substitutions are applied
    correctly, and every remaining sentence is tagged `(XX mock)` and the
    whole draft is prefixed with an explicit placeholder banner, so the
    output can never be mistaken for a real translation.
  - In `MOCK_MODE=false` (with `ANTHROPIC_API_KEY` set), the same function
    calls Claude (`claude-sonnet-5`) with the source text and the relevant
    glossary rules as context, and returns a real first-pass draft.

- **Glossary + market-rules validation (`src/engine.py`)** -- the real,
  testable "brain" of the demo:
  - `check_glossary_compliance` scans the source text for every brand
    glossary term (`data/synthetic/glossary.json`) that applies, and
    verifies the target language's handling rule was respected in the
    draft -- either the term survived untranslated (for "do not translate"
    terms) or the market's approved translation phrase is present (for
    terms that must be translated a specific way).
  - `apply_market_flags` reads `data/synthetic/market_rules.json` and
    attaches flags such as `requires_legal_review` (e.g. Germany, due to a
    fictional advertising-disclosure rule) or `requires_cultural_review`.

- **Flagged localization draft (`src/models.py`)** -- a `LocalizationDraft`
  dataclass carrying the draft text, glossary violations, flags, and review
  state.

- **Native reviewer approval workflow (`src/engine.py` + `app.py`)** -- a
  human reviewer (played by the demo user) approves or rejects each draft
  with notes. Every submission, approval, and rejection is a state
  transition.

- **Audit trail (`data/synthetic/audit_log.json`)** -- created at runtime;
  every state transition is appended with a timestamp, source id, target
  language, action, from/to status, and reviewer notes.
