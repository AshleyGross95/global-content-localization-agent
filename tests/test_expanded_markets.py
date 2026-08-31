"""Tests covering the release-scale seeded data: 12 source assets x 6 target
markets, glossary/market-rule coverage for the 3 newly added languages
(French, Brazilian Portuguese, Korean), and graceful handling of an
unconfigured/unknown target language.

Loads the actual seeded JSON files (not inline fixtures) so these tests
fail if the real data drifts from the release requirements.
"""

import json
import os

import pytest

from src.engine import (
    apply_market_flags,
    build_localization_draft,
    check_glossary_compliance,
    record_review_decision,
    submit_for_review,
    load_audit_log,
)
from src.models import (
    REVIEW_APPROVED,
    REVIEW_PENDING,
    REVIEW_REJECTED,
    REVIEW_REVISION_REQUESTED,
    LocalizationDraft,
)

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "synthetic"
)


def _load(filename):
    with open(os.path.join(_DATA_DIR, filename), "r", encoding="utf-8") as f:
        return json.load(f)


SOURCE_ASSETS = _load("source_content.json")
GLOSSARY = _load("glossary.json")
MARKET_RULES = _load("market_rules.json")

EXPECTED_MARKETS = {"es", "de", "ja", "fr", "pt-BR", "ko"}
NEW_MARKETS = {"fr", "pt-BR", "ko"}


# ---------------------------------------------------------------------------
# Seeded-data scale: exactly 12 assets x exactly 6 markets
# ---------------------------------------------------------------------------


def test_exactly_twelve_source_assets_well_formed():
    assert len(SOURCE_ASSETS) == 12
    ids = [a["id"] for a in SOURCE_ASSETS]
    assert len(ids) == len(set(ids)), "source asset ids must be unique"
    for asset in SOURCE_ASSETS:
        assert asset["id"]
        assert asset["title"]
        assert asset["asset_type"]
        assert asset["body"]


def test_exactly_six_target_markets_well_formed():
    assert len(MARKET_RULES) == 6
    assert set(MARKET_RULES.keys()) == EXPECTED_MARKETS
    for code, rules in MARKET_RULES.items():
        assert rules.get("market_name"), f"{code} missing market_name"
        assert isinstance(rules.get("requires_legal_review"), bool)
        assert isinstance(rules.get("requires_cultural_review"), bool)
        assert rules.get("formality_note"), f"{code} missing formality_note"
        if rules["requires_legal_review"]:
            assert rules.get("legal_review_reason")
        if rules["requires_cultural_review"]:
            assert rules.get("cultural_review_reason")


def test_glossary_covers_all_six_languages_for_every_term():
    for entry in GLOSSARY:
        for lang in EXPECTED_MARKETS:
            assert entry.get(lang), f"glossary term {entry.get('term')!r} missing {lang!r} rule"


def test_full_twelve_by_six_matrix_builds_drafts_without_error():
    """Every one of the 12 seeded assets, localized into all 6 markets,
    must produce a well-formed LocalizationDraft with no exception."""
    combos = 0
    for asset in SOURCE_ASSETS:
        for lang in MARKET_RULES:
            draft = build_localization_draft(
                asset, lang, GLOSSARY, MARKET_RULES, mock_mode=True
            )
            assert isinstance(draft, LocalizationDraft)
            assert draft.target_language == lang
            assert draft.source_id == asset["id"]
            assert draft.draft_text  # never empty
            assert isinstance(draft.glossary_violations, list)
            assert isinstance(draft.flags, list)
            assert draft.review_status == REVIEW_PENDING
            combos += 1
    assert combos == 12 * 6 == 72


# ---------------------------------------------------------------------------
# Glossary checks for the 3 new languages
# ---------------------------------------------------------------------------


SOURCE_TEXT = "Welcome to Northfield Cloud! Your Free Trial starts today."


def test_french_do_not_translate_term_altered_produces_violation():
    draft_text = "Bienvenue chez Nuage Northfield! Votre essai gratuit commence aujourd'hui."
    violations = check_glossary_compliance(SOURCE_TEXT, draft_text, "fr", GLOSSARY)
    assert len(violations) == 1
    assert "Northfield Cloud" in violations[0]


def test_french_approved_translation_present_no_violation():
    draft_text = "Bienvenue chez Northfield Cloud! Votre essai gratuit commence aujourd'hui."
    violations = check_glossary_compliance(SOURCE_TEXT, draft_text, "fr", GLOSSARY)
    assert violations == []


def test_portuguese_br_required_translation_missing_produces_violation():
    draft_text = "Bem-vindo ao Northfield Cloud! Sua oferta especial comeca hoje."
    violations = check_glossary_compliance(SOURCE_TEXT, draft_text, "pt-BR", GLOSSARY)
    assert len(violations) == 1
    assert "Free Trial" in violations[0]


def test_portuguese_br_approved_translation_present_no_violation():
    draft_text = "Bem-vindo ao Northfield Cloud! Seu teste gratuito comeca hoje."
    violations = check_glossary_compliance(SOURCE_TEXT, draft_text, "pt-BR", GLOSSARY)
    assert violations == []


def test_korean_do_not_translate_term_altered_produces_violation():
    draft_text = "노스필드 클라우드에 오신 것을 환영합니다! 무료 체험이 오늘 시작됩니다."
    # "Northfield Cloud" has been translated into Korean characters instead of
    # surviving verbatim, which the do-not-translate rule forbids.
    violations = check_glossary_compliance(SOURCE_TEXT, draft_text, "ko", GLOSSARY)
    assert len(violations) == 1
    assert "Northfield Cloud" in violations[0]


def test_korean_approved_translation_present_no_violation():
    draft_text = "Northfield Cloud에 오신 것을 환영합니다! 무료 체험이 오늘 시작됩니다."
    violations = check_glossary_compliance(SOURCE_TEXT, draft_text, "ko", GLOSSARY)
    assert violations == []


# ---------------------------------------------------------------------------
# Market-rule flag correctness for the 3 new markets
# ---------------------------------------------------------------------------


def test_french_market_requires_legal_review_only():
    flags = apply_market_flags("fr", MARKET_RULES)
    assert "requires_legal_review" in flags
    assert "requires_cultural_review" not in flags


def test_portuguese_br_market_requires_cultural_review_only():
    flags = apply_market_flags("pt-BR", MARKET_RULES)
    assert "requires_cultural_review" in flags
    assert "requires_legal_review" not in flags


def test_korean_market_requires_both_legal_and_cultural_review():
    flags = apply_market_flags("ko", MARKET_RULES)
    assert "requires_legal_review" in flags
    assert "requires_cultural_review" in flags


@pytest.mark.parametrize("lang", sorted(NEW_MARKETS))
def test_new_market_flags_match_source_json_exactly(lang):
    rules = MARKET_RULES[lang]
    flags = apply_market_flags(lang, MARKET_RULES)
    assert ("requires_legal_review" in flags) == rules["requires_legal_review"]
    assert ("requires_cultural_review" in flags) == rules["requires_cultural_review"]


# ---------------------------------------------------------------------------
# Mock-adapter / engine failure handling: unconfigured target language
# ---------------------------------------------------------------------------


UNCONFIGURED_LANGUAGE = "xx"  # not present in market_rules.json or glossary.json


def test_apply_market_flags_unconfigured_language_returns_no_flags_not_crash():
    flags = apply_market_flags(UNCONFIGURED_LANGUAGE, MARKET_RULES)
    assert flags == []


def test_glossary_check_unconfigured_language_returns_no_violations_not_crash():
    violations = check_glossary_compliance(
        SOURCE_TEXT, "some untranslated draft", UNCONFIGURED_LANGUAGE, GLOSSARY
    )
    assert violations == []


def test_build_localization_draft_unconfigured_language_fails_gracefully():
    """Requesting a language that isn't configured in market_rules.json or
    glossary.json must not crash the pipeline -- it should come back as a
    valid draft with no flags and no glossary violations (nothing to check
    against), still pending human review, rather than raising."""
    asset = SOURCE_ASSETS[0]
    draft = build_localization_draft(
        asset, UNCONFIGURED_LANGUAGE, GLOSSARY, MARKET_RULES, mock_mode=True
    )
    assert isinstance(draft, LocalizationDraft)
    assert draft.target_language == UNCONFIGURED_LANGUAGE
    assert draft.flags == []
    assert draft.glossary_violations == []
    assert draft.draft_text  # mock path still returns placeholder text
    assert draft.review_status == REVIEW_PENDING


# ---------------------------------------------------------------------------
# Revision-requested review state (distinct from approve/reject)
# ---------------------------------------------------------------------------


def _make_draft() -> LocalizationDraft:
    return LocalizationDraft(
        source_id="welcome-email-01",
        target_language="fr",
        draft_text="[FR DRAFT] ...",
        glossary_violations=[],
        flags=["requires_legal_review"],
    )


def test_localization_draft_accepts_revision_requested_status():
    draft = LocalizationDraft(
        source_id="welcome-email-01",
        target_language="ko",
        draft_text="[KO DRAFT] ...",
        review_status=REVIEW_REVISION_REQUESTED,
    )
    assert draft.review_status == REVIEW_REVISION_REQUESTED


def test_record_review_decision_revision_requested_is_distinct_from_reject(tmp_path):
    log_path = os.path.join(tmp_path, "audit_log.json")
    draft = _make_draft()

    submit_for_review(draft, audit_log_path=log_path)
    record_review_decision(
        draft,
        REVIEW_REVISION_REQUESTED,
        reviewer_notes="Formality register is off for this market; please redo.",
        audit_log_path=log_path,
    )

    assert draft.review_status == REVIEW_REVISION_REQUESTED
    assert draft.review_status != REVIEW_REJECTED
    assert draft.review_status != REVIEW_APPROVED

    log = load_audit_log(log_path)
    assert len(log) == 2
    assert log[1]["action"] == REVIEW_REVISION_REQUESTED
    assert log[1]["to_status"] == REVIEW_REVISION_REQUESTED


def test_revision_requested_draft_can_be_resubmitted_for_review(tmp_path):
    log_path = os.path.join(tmp_path, "audit_log.json")
    draft = _make_draft()

    submit_for_review(draft, audit_log_path=log_path)
    record_review_decision(
        draft, REVIEW_REVISION_REQUESTED, "please redo", audit_log_path=log_path
    )
    assert draft.review_status == REVIEW_REVISION_REQUESTED

    submit_for_review(draft, audit_log_path=log_path)
    assert draft.review_status == REVIEW_PENDING

    log = load_audit_log(log_path)
    assert len(log) == 3
    assert log[2]["action"] == "submitted"
    assert log[2]["from_status"] == REVIEW_REVISION_REQUESTED
    assert log[2]["to_status"] == REVIEW_PENDING
