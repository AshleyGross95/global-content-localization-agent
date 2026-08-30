"""Core, deterministic business logic for the Global Content Localization Agent.

Everything in this module is plain, testable Python: no LLM calls happen
here directly (those live behind src/llm.py). This module is responsible for:

  1. Orchestrating draft generation (delegating the actual text transform to
     src/llm.py, mock or live per MOCK_MODE).
  2. Checking a draft against the brand glossary rules for its target
     language (glossary.json) and producing glossary_violations.
  3. Applying per-market rule flags (market_rules.json) to a draft.
  4. Running the native-reviewer approval workflow (submit / approve /
     reject) and appending every state transition, with a timestamp, to
     data/synthetic/audit_log.json.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src import llm
from src.models import (
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    LocalizationDraft,
)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
DEFAULT_AUDIT_LOG_PATH = os.path.join(_REPO_ROOT, "data", "synthetic", "audit_log.json")


# ---------------------------------------------------------------------------
# Draft generation
# ---------------------------------------------------------------------------


def build_localization_draft(
    source_asset: Dict,
    target_language: str,
    glossary: List[Dict],
    market_rules: Dict[str, Dict],
    mock_mode: Optional[bool] = None,
) -> LocalizationDraft:
    """Generate a LocalizationDraft for one source asset + target language.

    Runs the translation layer (mock or live, per MOCK_MODE), then applies
    the glossary check and market-rule flags on top of the resulting text.
    """
    draft_text = llm.generate_localized_draft(
        source_asset["body"], target_language, glossary, mock_mode=mock_mode
    )
    violations = check_glossary_compliance(
        source_asset["body"], draft_text, target_language, glossary
    )
    flags = apply_market_flags(target_language, market_rules)

    return LocalizationDraft(
        source_id=source_asset["id"],
        target_language=target_language,
        draft_text=draft_text,
        glossary_violations=violations,
        flags=flags,
        review_status=REVIEW_PENDING,
        reviewer_notes=None,
    )


# ---------------------------------------------------------------------------
# Glossary compliance
# ---------------------------------------------------------------------------


def check_glossary_compliance(
    source_text: str,
    draft_text: str,
    target_language: str,
    glossary: List[Dict],
) -> List[str]:
    """Check a localized draft against the brand glossary for its language.

    For every glossary term that is actually present in the source text
    (i.e. relevant to this asset), verify the market's handling rule:

      - "do not translate" terms must appear verbatim (case-insensitive) in
        the draft. If they don't, that's a violation (the term was altered
        or dropped).
      - "use approved translation: <phrase>" terms must have that approved
        phrase present (case-insensitive) in the draft. If it's missing,
        that's a violation (the required localized term is absent).

    Returns a list of human-readable violation strings (empty if compliant).
    """
    violations: List[str] = []

    for entry in glossary:
        term = entry.get("term")
        rule = entry.get(target_language)
        if not term or not rule:
            continue

        # Only relevant if the term actually appears in this source asset.
        if not re.search(re.escape(term), source_text, flags=re.IGNORECASE):
            continue

        rule_lower = rule.lower()

        if "do not translate" in rule_lower:
            if not re.search(re.escape(term), draft_text, flags=re.IGNORECASE):
                violations.append(
                    f"'{term}' must remain untranslated (do-not-translate term) but was "
                    f"not found as-is in the {target_language} draft."
                )
        elif "use approved translation" in rule_lower and ":" in rule:
            approved = rule.split(":", 1)[1].strip().strip("'\"")
            if approved and not re.search(
                re.escape(approved), draft_text, flags=re.IGNORECASE
            ):
                violations.append(
                    f"'{term}' requires the approved {target_language} translation "
                    f"'{approved}', which was not found in the draft."
                )

    return violations


# ---------------------------------------------------------------------------
# Market-rule flags
# ---------------------------------------------------------------------------


def apply_market_flags(target_language: str, market_rules: Dict[str, Dict]) -> List[str]:
    """Translate market_rules.json booleans into a list of flag strings."""
    rules = market_rules.get(target_language, {})
    flags: List[str] = []
    if rules.get("requires_legal_review"):
        flags.append("requires_legal_review")
    if rules.get("requires_cultural_review"):
        flags.append("requires_cultural_review")
    return flags


# ---------------------------------------------------------------------------
# Reviewer workflow + audit log
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_audit_log(path: Optional[str] = None) -> List[Dict]:
    """Load the audit log, returning an empty list if it doesn't exist yet."""
    path = path or DEFAULT_AUDIT_LOG_PATH
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _append_audit_entry(entry: Dict, path: Optional[str] = None) -> None:
    path = path or DEFAULT_AUDIT_LOG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    log = load_audit_log(path)
    log.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def submit_for_review(
    draft: LocalizationDraft, audit_log_path: Optional[str] = None
) -> LocalizationDraft:
    """Submit a draft for native-reviewer approval, logging the transition."""
    previous_status = draft.review_status
    draft.review_status = REVIEW_PENDING
    draft.reviewer_notes = None

    _append_audit_entry(
        {
            "timestamp": _now_iso(),
            "source_id": draft.source_id,
            "target_language": draft.target_language,
            "action": "submitted",
            "from_status": previous_status,
            "to_status": REVIEW_PENDING,
            "notes": None,
        },
        path=audit_log_path,
    )
    return draft


def record_review_decision(
    draft: LocalizationDraft,
    decision: str,
    reviewer_notes: str = "",
    audit_log_path: Optional[str] = None,
) -> LocalizationDraft:
    """Approve or reject a draft, logging the transition to the audit log."""
    if decision not in (REVIEW_APPROVED, REVIEW_REJECTED):
        raise ValueError(
            f"decision must be '{REVIEW_APPROVED}' or '{REVIEW_REJECTED}', got {decision!r}"
        )

    previous_status = draft.review_status
    draft.review_status = decision
    draft.reviewer_notes = reviewer_notes or None

    _append_audit_entry(
        {
            "timestamp": _now_iso(),
            "source_id": draft.source_id,
            "target_language": draft.target_language,
            "action": decision,
            "from_status": previous_status,
            "to_status": decision,
            "notes": reviewer_notes or None,
        },
        path=audit_log_path,
    )
    return draft
