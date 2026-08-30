"""Tests for src/engine.py -- the deterministic core of the localization demo."""

import json
import os

import pytest

from src.engine import (
    apply_market_flags,
    build_localization_draft,
    check_glossary_compliance,
    load_audit_log,
    record_review_decision,
    submit_for_review,
)
from src.models import REVIEW_APPROVED, REVIEW_PENDING, REVIEW_REJECTED, LocalizationDraft

GLOSSARY = [
    {
        "term": "Northfield Cloud",
        "es": "do not translate, keep as-is",
        "de": "do not translate, keep as-is",
    },
    {
        "term": "Free Trial",
        "es": "use approved translation: prueba gratuita",
        "de": "use approved translation: kostenlose Testversion",
    },
]

MARKET_RULES = {
    "es": {"requires_legal_review": False, "requires_cultural_review": True},
    "de": {"requires_legal_review": True, "requires_cultural_review": False},
}

SOURCE_TEXT = "Welcome to Northfield Cloud! Your Free Trial starts today."


# ---------------------------------------------------------------------------
# Glossary compliance
# ---------------------------------------------------------------------------


def test_do_not_translate_term_left_untouched_produces_no_violation():
    draft_text = "Bienvenido a Northfield Cloud! Su prueba gratuita comienza hoy."
    violations = check_glossary_compliance(SOURCE_TEXT, draft_text, "es", GLOSSARY)
    assert violations == []


def test_do_not_translate_term_altered_produces_violation():
    # "Northfield Cloud" has been translated/altered, which it never should be.
    draft_text = "Bienvenido a Nube Northfield! Su prueba gratuita comienza hoy."
    violations = check_glossary_compliance(SOURCE_TEXT, draft_text, "es", GLOSSARY)
    assert len(violations) == 1
    assert "Northfield Cloud" in violations[0]


def test_required_translation_missing_produces_violation():
    # "Northfield Cloud" is fine, but the approved Spanish phrase for
    # "Free Trial" never shows up in the draft.
    draft_text = "Bienvenido a Northfield Cloud! Su oferta especial comienza hoy."
    violations = check_glossary_compliance(SOURCE_TEXT, draft_text, "es", GLOSSARY)
    assert len(violations) == 1
    assert "Free Trial" in violations[0]


def test_glossary_check_ignores_terms_not_present_in_source():
    # Glossary term not present in this particular source text should be
    # skipped entirely, even if the language rule is missing/unknown.
    other_source = "This message never mentions the brand or the trial."
    violations = check_glossary_compliance(other_source, "some draft", "es", GLOSSARY)
    assert violations == []


# ---------------------------------------------------------------------------
# Market-rule flags
# ---------------------------------------------------------------------------


def test_german_market_carries_requires_legal_review_flag():
    flags = apply_market_flags("de", MARKET_RULES)
    assert "requires_legal_review" in flags
    assert "requires_cultural_review" not in flags


def test_spanish_market_carries_cultural_review_not_legal_review():
    flags = apply_market_flags("es", MARKET_RULES)
    assert "requires_cultural_review" in flags
    assert "requires_legal_review" not in flags


def test_build_localization_draft_attaches_market_flags():
    source_asset = {"id": "welcome-email-01", "body": SOURCE_TEXT}
    draft = build_localization_draft(
        source_asset, "de", GLOSSARY, MARKET_RULES, mock_mode=True
    )
    assert isinstance(draft, LocalizationDraft)
    assert draft.target_language == "de"
    assert "requires_legal_review" in draft.flags
    assert draft.review_status == REVIEW_PENDING


# ---------------------------------------------------------------------------
# Reviewer workflow + audit log
# ---------------------------------------------------------------------------


def _make_draft() -> LocalizationDraft:
    return LocalizationDraft(
        source_id="welcome-email-01",
        target_language="de",
        draft_text="[DE DRAFT] ...",
        glossary_violations=[],
        flags=["requires_legal_review"],
    )


def test_submit_for_review_logs_pending_transition(tmp_path):
    log_path = os.path.join(tmp_path, "audit_log.json")
    draft = _make_draft()

    submit_for_review(draft, audit_log_path=log_path)

    assert draft.review_status == REVIEW_PENDING
    log = load_audit_log(log_path)
    assert len(log) == 1
    assert log[0]["action"] == "submitted"
    assert log[0]["to_status"] == REVIEW_PENDING
    assert "timestamp" in log[0]


def test_approve_workflow_appends_correct_status_transition(tmp_path):
    log_path = os.path.join(tmp_path, "audit_log.json")
    draft = _make_draft()

    submit_for_review(draft, audit_log_path=log_path)
    record_review_decision(
        draft, REVIEW_APPROVED, reviewer_notes="Looks good.", audit_log_path=log_path
    )

    assert draft.review_status == REVIEW_APPROVED
    assert draft.reviewer_notes == "Looks good."

    log = load_audit_log(log_path)
    assert len(log) == 2
    assert log[1]["action"] == REVIEW_APPROVED
    assert log[1]["from_status"] == REVIEW_PENDING
    assert log[1]["to_status"] == REVIEW_APPROVED
    assert log[1]["notes"] == "Looks good."


def test_reject_workflow_appends_correct_status_transition(tmp_path):
    log_path = os.path.join(tmp_path, "audit_log.json")
    draft = _make_draft()

    submit_for_review(draft, audit_log_path=log_path)
    record_review_decision(
        draft,
        REVIEW_REJECTED,
        reviewer_notes="Register is too informal for this market.",
        audit_log_path=log_path,
    )

    assert draft.review_status == REVIEW_REJECTED
    log = load_audit_log(log_path)
    assert len(log) == 2
    assert log[1]["action"] == REVIEW_REJECTED
    assert log[1]["from_status"] == REVIEW_PENDING
    assert log[1]["to_status"] == REVIEW_REJECTED


def test_record_review_decision_rejects_invalid_decision(tmp_path):
    log_path = os.path.join(tmp_path, "audit_log.json")
    draft = _make_draft()
    with pytest.raises(ValueError):
        record_review_decision(draft, "maybe", audit_log_path=log_path)


def test_audit_log_is_valid_json_on_disk(tmp_path):
    log_path = os.path.join(tmp_path, "audit_log.json")
    draft = _make_draft()
    submit_for_review(draft, audit_log_path=log_path)
    record_review_decision(draft, REVIEW_APPROVED, "ok", audit_log_path=log_path)

    with open(log_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 2
