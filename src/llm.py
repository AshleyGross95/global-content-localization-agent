"""LLM adapter for the Global Content Localization Agent demo.

Mock path (default, MOCK_MODE=true): deterministic, rule-based placeholder
localization. No network calls, no API key required. The output is a
clearly-labeled placeholder draft -- it is NOT a real machine translation
and must never be mistaken for production-quality localization output.

Live path (MOCK_MODE=false and ANTHROPIC_API_KEY set): calls Claude via the
`anthropic` Python SDK (model "claude-sonnet-5") to generate a real
localization draft, given the source text and the brand glossary rules for
the target language as context.

Either path returns a plain draft string; src/engine.py is responsible for
running the deterministic glossary check and market-rule flagging on top of
whatever draft text comes back from here.
"""

from __future__ import annotations

import os
import re
from typing import Optional

LANGUAGE_LABELS = {
    "es": "Spanish",
    "de": "German",
    "ja": "Japanese",
}


def is_mock_mode() -> bool:
    """Read MOCK_MODE from the environment. Defaults to True (mock)."""
    return os.environ.get("MOCK_MODE", "true").strip().lower() not in (
        "false",
        "0",
        "no",
    )


def generate_localized_draft(
    source_text: str,
    target_language: str,
    glossary: Optional[list] = None,
    mock_mode: Optional[bool] = None,
) -> str:
    """Produce a localized draft of `source_text` for `target_language`.

    If mock_mode is None, it is read from the MOCK_MODE env var.
    """
    if mock_mode is None:
        mock_mode = is_mock_mode()
    glossary = glossary or []

    if mock_mode:
        return _mock_translate(source_text, target_language, glossary)
    return _live_translate(source_text, target_language, glossary)


def _mock_translate(source_text: str, target_language: str, glossary: list) -> str:
    """Deterministic, rule-based placeholder localization.

    This is intentionally NOT a real machine translation. It:
      1. Applies the brand glossary's approved-translation / do-not-translate
         rules for the target language (the one piece of "translation" that
         genuinely needs to be correct for the demo to be meaningful).
      2. Tags every other sentence with a visible "(mock)" marker so nobody
         mistakes the remaining body copy for a real translation.
      3. Prefixes the whole draft with an explicit placeholder banner.
    """
    lang_code = target_language.upper()
    working_text = source_text

    for entry in glossary:
        term = entry.get("term")
        rule = entry.get(target_language)
        if not term or not rule:
            continue
        rule_lower = rule.lower()
        if "do not translate" in rule_lower:
            # No change: the term must survive verbatim.
            continue
        if "use approved translation" in rule_lower and ":" in rule:
            approved = rule.split(":", 1)[1].strip().strip("'\"")
            if approved and re.search(re.escape(term), working_text, flags=re.IGNORECASE):
                working_text = re.sub(
                    re.escape(term), approved, working_text, flags=re.IGNORECASE
                )

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", working_text) if s.strip()]
    tagged = " ".join(f"{s} ({lang_code} mock)" for s in sentences) if sentences else working_text

    banner = (
        f"[{lang_code} DRAFT — MOCK PLACEHOLDER, NOT A REAL TRANSLATION. "
        f"Set MOCK_MODE=false with ANTHROPIC_API_KEY to generate a real draft via Claude.]"
    )
    return f"{banner}\n{tagged}"


def _live_translate(source_text: str, target_language: str, glossary: list) -> str:
    """Real localization draft via the Claude API (live mode only)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "MOCK_MODE is false but ANTHROPIC_API_KEY is not set. "
            "Set ANTHROPIC_API_KEY in your .env, or leave MOCK_MODE=true to use the "
            "deterministic placeholder path."
        )

    from anthropic import Anthropic  # imported lazily so mock mode has no hard dependency

    client = Anthropic(api_key=api_key)
    lang_label = LANGUAGE_LABELS.get(target_language, target_language)

    glossary_lines = []
    for entry in glossary:
        rule = entry.get(target_language)
        if rule:
            glossary_lines.append(f"- {entry.get('term')}: {rule}")
    glossary_block = "\n".join(glossary_lines) if glossary_lines else "(no glossary terms apply)"

    prompt = (
        f"You are producing a first-pass localization draft of English marketing/product "
        f"copy into {lang_label}, for internal review by a native-speaking reviewer before "
        f"publication. This is a draft, not a final approved translation.\n\n"
        f"Brand glossary rules to follow exactly for this language:\n{glossary_block}\n\n"
        f"Source text:\n{source_text}\n\n"
        f"Return only the localized draft text, with no commentary."
    )

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
