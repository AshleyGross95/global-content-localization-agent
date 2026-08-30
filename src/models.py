"""Domain data model for the Global Content Localization Agent demo.

Synthetic-data-only portfolio demo. No real company, client, or person
data is used anywhere in this repo.
"""

from dataclasses import dataclass, field
from typing import List, Optional

# review_status is a simple "enum-like" str with three valid values.
REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"

VALID_REVIEW_STATUSES = (REVIEW_PENDING, REVIEW_APPROVED, REVIEW_REJECTED)


@dataclass
class LocalizationDraft:
    """A single localized draft of one source asset for one target language.

    Attributes:
        source_id: id of the source asset this draft was generated from
            (see data/synthetic/source_content.json).
        target_language: ISO-ish language code for the target market
            (e.g. "es", "de", "ja").
        draft_text: the localized draft text. In MOCK_MODE this is a
            clearly-labeled placeholder transform, never a real translation.
        glossary_violations: human-readable strings describing any brand
            glossary rule that this draft appears to violate.
        flags: market-rule flags attached to this draft, e.g.
            "requires_legal_review" or "requires_cultural_review".
        review_status: one of "pending" | "approved" | "rejected".
        reviewer_notes: free-text notes left by the native reviewer,
            required in practice for a rejection, optional for an approval.
    """

    source_id: str
    target_language: str
    draft_text: str
    glossary_violations: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    review_status: str = REVIEW_PENDING
    reviewer_notes: Optional[str] = None

    def __post_init__(self) -> None:
        if self.review_status not in VALID_REVIEW_STATUSES:
            raise ValueError(
                f"Invalid review_status {self.review_status!r}; "
                f"must be one of {VALID_REVIEW_STATUSES}"
            )
