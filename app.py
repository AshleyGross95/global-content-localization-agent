"""Global Content Localization Agent -- Streamlit demo.

Pick a source marketing asset and one or more target languages, generate
localized drafts, see the brand-glossary check and market-rule flags for
each, then play the native-reviewer role: approve, reject, or request
revision on each draft with notes, and inspect the resulting audit trail.

Runs entirely on synthetic data. See README.md for the full walkthrough.
"""

import json
import os

import streamlit as st

from src.engine import (
    build_localization_draft,
    load_audit_log,
    record_review_decision,
    submit_for_review,
)
from src.llm import is_mock_mode
from src.models import (
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    REVIEW_REVISION_REQUESTED,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "synthetic")
AUDIT_LOG_PATH = os.path.join(DATA_DIR, "audit_log.json")

LANGUAGE_LABELS = {
    "es": "Spanish (es)",
    "de": "German (de)",
    "ja": "Japanese (ja)",
    "fr": "French (fr)",
    "pt-BR": "Portuguese, Brazil (pt-BR)",
    "ko": "Korean (ko)",
}

# Hardcoded to the actual verified `pytest -v` count for this repo (tests/test_engine.py
# + tests/test_expanded_markets.py) -- update this literal if the test suite grows.
VERIFIED_TEST_COUNT = 34

st.set_page_config(page_title="Global Content Localization Agent", page_icon="🌐", layout="wide")


@st.cache_data
def load_json(filename: str):
    with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as f:
        return json.load(f)


source_assets = load_json("source_content.json")
glossary = load_json("glossary.json")
market_rules = load_json("market_rules.json")

if "drafts" not in st.session_state:
    st.session_state.drafts = {}  # key: (source_id, target_language) -> LocalizationDraft

# ---------------------------------------------------------------------------
# Header + mode banner
# ---------------------------------------------------------------------------

st.title("Global Content Localization Agent")
st.caption(
    "Localizes source marketing copy for target markets, checks it against a brand "
    "glossary, flags markets needing legal/cultural review, and routes drafts through "
    "a native-reviewer approval workflow with a full audit trail."
)
st.markdown("**Public portfolio prototype · Synthetic data**")

metric_cols = st.columns(4)
with metric_cols[0]:
    # Literal count of records in data/synthetic/source_content.json.
    st.metric("Source assets", len(source_assets))
with metric_cols[1]:
    # Literal count of keys in data/synthetic/market_rules.json.
    st.metric("Target markets", len(market_rules))
with metric_cols[2]:
    # Hardcoded to the verified `pytest -v` count -- see VERIFIED_TEST_COUNT above.
    st.metric("Localization/review tests", VERIFIED_TEST_COUNT)
with metric_cols[3]:
    if st.button("Reset state", help="Clears the session audit log and all generated drafts back to empty."):
        st.session_state.drafts = {}
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
        st.success("Session audit log and drafts reset to empty.")
        st.rerun()

mock_mode = is_mock_mode()
if mock_mode:
    st.info(
        "**MOCK_MODE is ON (default).** Localized drafts below are a deterministic, "
        "clearly-labeled **placeholder transform** -- not a real machine translation. "
        "Set `MOCK_MODE=false` and `ANTHROPIC_API_KEY` in a `.env` file to generate real "
        "draft text via Claude (`src/llm.py`) instead.",
        icon="🧪",
    )
else:
    st.success(
        "**MOCK_MODE is OFF.** Localized drafts are generated live via the Claude API "
        "(`claude-sonnet-5`). They are still first-pass drafts for reviewer sign-off, not "
        "final approved translations.",
        icon="✅",
    )

with st.expander("Translation vs. transcreation vs. legal review vs. native-speaker QA"):
    st.markdown(
        """
This demo intentionally keeps four distinct localization steps separate, because
conflating them is a common (and costly) real-world mistake:

- **Translation** -- converting source text into a target language, term for term
  and sentence for sentence. That's all this demo's mock/live draft step claims to do.
- **Transcreation** -- adapting the *creative intent* of copy (tone, wordplay, imagery)
  for a target culture, sometimes departing significantly from a literal translation.
  This demo does **not** attempt transcreation; it produces a literal draft only.
- **Legal / regulatory review** -- checking market-specific disclosure, advertising, or
  compliance requirements (e.g. this demo's fictional German advertising-disclosure
  rule). Flagged automatically via `market_rules.json`, but the actual review is a
  human legal step outside this tool.
- **Native-speaker QA** -- a fluent reviewer confirming the draft reads naturally,
  respects register/formality norms, and contains no embarrassing errors. That's the
  reviewer panel below -- you, playing that role.

None of these four steps substitutes for another. A glossary check passing does not
mean a draft is transcreated, legally cleared, or naturally-worded.
        """
    )

st.divider()

# ---------------------------------------------------------------------------
# 1. Pick source asset + target languages
# ---------------------------------------------------------------------------

st.header("1. Generate localized drafts")

col1, col2 = st.columns([2, 2])

with col1:
    asset_labels = {a["id"]: f"{a['title']} ({a['id']})" for a in source_assets}
    selected_asset_id = st.selectbox(
        "Source asset", options=list(asset_labels.keys()), format_func=lambda i: asset_labels[i]
    )
    selected_asset = next(a for a in source_assets if a["id"] == selected_asset_id)
    st.text_area("Source text (English)", value=selected_asset["body"], height=140, disabled=True)

with col2:
    selected_languages = st.multiselect(
        "Target language(s)",
        options=list(market_rules.keys()),
        default=list(market_rules.keys()),
        format_func=lambda code: LANGUAGE_LABELS.get(code, code),
    )
    st.caption("Market rules applied per language:")
    for code in selected_languages:
        rules = market_rules.get(code, {})
        st.write(f"**{LANGUAGE_LABELS.get(code, code)}** -- {rules.get('formality_note', '')}")

generate_clicked = st.button("Generate localized draft(s)", type="primary")

if generate_clicked:
    for lang in selected_languages:
        draft = build_localization_draft(selected_asset, lang, glossary, market_rules)
        submit_for_review(draft, audit_log_path=AUDIT_LOG_PATH)
        st.session_state.drafts[(selected_asset["id"], lang)] = draft
    st.success(f"Generated {len(selected_languages)} draft(s) for '{selected_asset['title']}'.")

st.divider()

# ---------------------------------------------------------------------------
# 2. Draft results: glossary check + flags
# ---------------------------------------------------------------------------

st.header("2. Draft results")
st.info(
    "These localization drafts (mock or live) do not replace legal, regulatory, or "
    "local-market review. Glossary checks and market-rule flags below catch specific, "
    "narrow issues only -- a clean result is not legal sign-off, cultural sign-off, or "
    "confirmation the copy reads naturally to a native speaker.",
    icon="⚖️",
)

current_keys = [
    key for key in st.session_state.drafts if key[0] == selected_asset["id"]
]

if not current_keys:
    st.caption("No drafts generated yet for this source asset. Use the button above.")
else:
    for key in current_keys:
        draft = st.session_state.drafts[key]
        lang_label = LANGUAGE_LABELS.get(draft.target_language, draft.target_language)
        with st.container(border=True):
            st.subheader(lang_label)
            st.text_area(
                "Localized draft", value=draft.draft_text, height=140, key=f"draft_text_{key}"
            )

            badge_cols = st.columns(3)
            with badge_cols[0]:
                st.metric("Review status", draft.review_status)
            with badge_cols[1]:
                st.metric("Glossary violations", len(draft.glossary_violations))
            with badge_cols[2]:
                st.metric("Flags", len(draft.flags))

            if draft.glossary_violations:
                st.warning("Glossary violations:\n" + "\n".join(f"- {v}" for v in draft.glossary_violations))
            else:
                st.caption("No glossary violations detected.")

            if draft.flags:
                for flag in draft.flags:
                    if flag == "requires_legal_review":
                        reason = market_rules.get(draft.target_language, {}).get(
                            "legal_review_reason", ""
                        )
                        st.error(f"🚩 requires_legal_review -- {reason}")
                    elif flag == "requires_cultural_review":
                        reason = market_rules.get(draft.target_language, {}).get(
                            "cultural_review_reason", ""
                        )
                        st.warning(f"🚩 requires_cultural_review -- {reason}")
                    else:
                        st.warning(f"🚩 {flag}")
            else:
                st.caption("No market-rule flags for this language.")

st.divider()

# ---------------------------------------------------------------------------
# 3. Native reviewer panel
# ---------------------------------------------------------------------------

st.header("3. Native reviewer panel")
st.caption(
    "Play the native-speaker reviewer role: approve, reject, or request revision on each "
    "pending draft, with notes."
)

pending_keys = [
    key for key, d in st.session_state.drafts.items() if d.review_status == REVIEW_PENDING
]

if not pending_keys:
    st.caption("No drafts awaiting review.")
else:
    for key in pending_keys:
        draft = st.session_state.drafts[key]
        lang_label = LANGUAGE_LABELS.get(draft.target_language, draft.target_language)
        with st.container(border=True):
            st.write(f"**{draft.source_id} -> {lang_label}** (status: {draft.review_status})")
            notes = st.text_area("Reviewer notes", key=f"notes_{key}", height=80)
            btn_cols = st.columns(3)
            with btn_cols[0]:
                if st.button("Approve", key=f"approve_{key}"):
                    record_review_decision(
                        draft, REVIEW_APPROVED, notes, audit_log_path=AUDIT_LOG_PATH
                    )
                    st.rerun()
            with btn_cols[1]:
                if st.button("Request revision", key=f"revise_{key}"):
                    record_review_decision(
                        draft, REVIEW_REVISION_REQUESTED, notes, audit_log_path=AUDIT_LOG_PATH
                    )
                    st.rerun()
            with btn_cols[2]:
                if st.button("Reject", key=f"reject_{key}"):
                    record_review_decision(
                        draft, REVIEW_REJECTED, notes, audit_log_path=AUDIT_LOG_PATH
                    )
                    st.rerun()

reviewed_keys = [
    key for key, d in st.session_state.drafts.items() if d.review_status != REVIEW_PENDING
]
STATUS_ICONS = {
    REVIEW_APPROVED: "✅",
    REVIEW_REJECTED: "❌",
    REVIEW_REVISION_REQUESTED: "✏️",
}
if reviewed_keys:
    st.caption("Reviewed drafts:")
    for key in reviewed_keys:
        draft = st.session_state.drafts[key]
        lang_label = LANGUAGE_LABELS.get(draft.target_language, draft.target_language)
        status_icon = STATUS_ICONS.get(draft.review_status, "•")
        row_cols = st.columns([4, 1])
        with row_cols[0]:
            st.write(
                f"{status_icon} **{draft.source_id} -> {lang_label}**: {draft.review_status} "
                f"-- \"{draft.reviewer_notes or ''}\""
            )
        with row_cols[1]:
            if draft.review_status in (REVIEW_REJECTED, REVIEW_REVISION_REQUESTED):
                if st.button("Resubmit for review", key=f"resubmit_{key}"):
                    submit_for_review(draft, audit_log_path=AUDIT_LOG_PATH)
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# 4. Audit trail
# ---------------------------------------------------------------------------

st.header("4. Audit trail")
st.caption(f"Full history of state transitions, persisted to `data/synthetic/audit_log.json`.")

audit_log = load_audit_log(AUDIT_LOG_PATH)
if not audit_log:
    st.caption("No audit events yet. Generate a draft above to get started.")
else:
    st.dataframe(audit_log, use_container_width=True, hide_index=True)
