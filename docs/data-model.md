# Data model

All persistent state in this demo is either a static synthetic seed file
(source content, glossary, market rules) or a runtime-generated record
(the in-memory `LocalizationDraft` and the on-disk audit log). Nothing here
is a real database -- everything is JSON on disk plus Streamlit session
state, matching the "prototype" maturity of this demo (see
`docs/limitations.md`).

## Seeded record shapes

### `data/synthetic/source_content.json` -- 12 records

A flat JSON array of fictional English source assets. Each record:

```json
{
  "id": "welcome-email-01",
  "title": "Product Launch Email",
  "asset_type": "marketing email",
  "body": "Welcome to Northfield Cloud! ..."
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique, kebab-case, used as the key for drafts and audit-log rows. |
| `title` | string | Human-readable label shown in the source-asset picker. |
| `asset_type` | string | Free-text content category, e.g. `marketing email`, `landing page`, `transactional notice`, `product description`, `UI microcopy`, `social caption`, `push notification`, `in-app onboarding tooltip`, `customer support macro`, `blog post intro`, `help center article`. |
| `body` | string | The fictional English source copy to be localized. |

The 12 seeded assets deliberately span this range of asset types (verified
in `tests/test_expanded_markets.py::test_exactly_twelve_source_assets_well_formed`),
so the demo shows localization/review working across more than one kind of
copy, not just marketing email.

### `data/synthetic/glossary.json` -- 10 brand-term records x 6 languages

A flat JSON array of glossary terms. Each record carries one handling rule
per target language:

```json
{
  "term": "Free Trial",
  "note": "Generic term, should use the market's approved translation.",
  "es": "use approved translation: prueba gratuita",
  "de": "use approved translation: kostenlose Testversion",
  "ja": "use approved translation: 無料トライアル",
  "fr": "use approved translation: essai gratuit",
  "pt-BR": "use approved translation: teste gratuito",
  "ko": "use approved translation: 무료 체험"
}
```

| Field | Type | Notes |
|---|---|---|
| `term` | string | The English brand/generic term as it appears in source copy. |
| `note` | string | Human-readable rationale, not used by code. |
| `<lang>` (`es`, `de`, `ja`, `fr`, `pt-BR`, `ko`) | string | The handling rule for that market. Always one of two shapes (see below). |

Two rule shapes, parsed by `src/engine.py::check_glossary_compliance` and
`src/llm.py::_mock_translate`:

- `"do not translate, keep as-is"` -- the term (e.g. `Northfield Cloud`,
  `Nimbus Sync`, `Premium Plan`, `Northfield ID`) must appear verbatim,
  case-insensitively, in the localized draft.
- `"use approved translation: <phrase>"` -- the exact approved phrase after
  the colon must appear, case-insensitively, in the localized draft.

Every term carries a rule for all 6 languages
(`tests/test_expanded_markets.py::test_glossary_covers_all_six_languages_for_every_term`).

### `data/synthetic/market_rules.json` -- 6 market records

A JSON object keyed by language/market code. Each value:

```json
{
  "market_name": "Germany (German)",
  "requires_legal_review": true,
  "legal_review_reason": "Fictional EU-DE Advertising Disclosure Rule (ADR-7): ...",
  "requires_cultural_review": false,
  "formality_note": "Use formal register (Sie) in German business communications; avoid the informal 'du' form."
}
```

| Field | Type | Notes |
|---|---|---|
| `market_name` | string | Human-readable market label. |
| `requires_legal_review` | bool | Drives the `requires_legal_review` flag in `apply_market_flags`. |
| `legal_review_reason` | string | Required when `requires_legal_review` is true; shown in the UI next to the flag. |
| `requires_cultural_review` | bool | Drives the `requires_cultural_review` flag. |
| `cultural_review_reason` | string | Required when `requires_cultural_review` is true. |
| `formality_note` | string | Register/formality guidance shown in the UI; informational only, not enforced by code. |

The 6 seeded markets are `es` (Spain), `de` (Germany), `ja` (Japan), `fr`
(France), `pt-BR` (Brazil), and `ko` (South Korea) -- see
`tests/test_expanded_markets.py::test_exactly_six_target_markets_well_formed`.
All legal/cultural rules are fictional, invented for this demo (e.g. "ADR-7",
"Loi ABC-12", "KEC-15") and do not correspond to real regulations.

## Runtime record shapes

### `LocalizationDraft` (`src/models.py`)

```python
@dataclass
class LocalizationDraft:
    source_id: str
    target_language: str
    draft_text: str
    glossary_violations: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    review_status: str = REVIEW_PENDING
    reviewer_notes: Optional[str] = None
```

`review_status` is one of four literal values, validated in
`__post_init__`:

| Constant | Value | Meaning |
|---|---|---|
| `REVIEW_PENDING` | `"pending"` | Awaiting a reviewer decision. Default on creation and after resubmission. |
| `REVIEW_APPROVED` | `"approved"` | Reviewer signed off; terminal for this demo. |
| `REVIEW_REJECTED` | `"rejected"` | Reviewer rejected outright; can be resubmitted after rework. |
| `REVIEW_REVISION_REQUESTED` | `"revision_requested"` | Reviewer wants specific changes, distinct from a hard rejection; can be resubmitted after rework. |

`LocalizationDraft` instances live only in `st.session_state.drafts` for the
duration of a browser session -- they are not persisted to disk (see
`docs/limitations.md`).

### Audit log entries (`data/synthetic/audit_log.json`)

Created at runtime by `src/engine.py`. A flat JSON array; each entry is
appended, never mutated or removed (except by the in-app "Reset state"
button, which truncates the file back to `[]`):

```json
{
  "timestamp": "2026-08-30T12:00:00+00:00",
  "source_id": "welcome-email-01",
  "target_language": "de",
  "action": "approved",
  "from_status": "pending",
  "to_status": "approved",
  "notes": "Looks good."
}
```

| Field | Type | Notes |
|---|---|---|
| `timestamp` | string | ISO 8601, UTC, from `datetime.now(timezone.utc).isoformat()`. |
| `source_id` | string | Matches a `source_content.json` id. |
| `target_language` | string | Matches a `market_rules.json` key. |
| `action` | string | `"submitted"`, `"approved"`, `"rejected"`, or `"revision_requested"`. |
| `from_status` / `to_status` | string | The review-status transition. |
| `notes` | string or null | Reviewer notes, if any. |
