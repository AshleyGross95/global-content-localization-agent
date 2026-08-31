# Demo script (60-90 seconds)

A guided walkthrough a reader can follow verbatim, right after running
`streamlit run app.py`.

---

**0:00 -- Orient.**
Point out the "Public portfolio prototype · Synthetic data" line under the
title, and the three-metric row: **12 source assets · 6 target markets ·
34 localization/review tests**. Note the `MOCK_MODE is ON` banner --
everything below runs with zero API keys, on deterministic placeholder
translation.

**0:10 -- Pick content and markets.**
In section 1, "Generate localized drafts," leave the source asset on
"Product Launch Email" and leave all 6 target languages selected (Spanish,
German, Japanese, French, Brazilian Portuguese, Korean). Read the
formality note shown for German ("Use formal register (Sie)...") and Korean
("Use formal honorific speech...") -- these come straight from
`market_rules.json`, not hardcoded copy.

**0:25 -- Generate.**
Click "Generate localized draft(s)." Six drafts appear in section 2.

**0:35 -- Inspect one flagged draft.**
Scroll to the German draft. It shows `0` glossary violations (the brand
terms "Northfield Cloud," "Nimbus Sync," and "Premium Plan" were correctly
left untranslated, and "Free Trial" was correctly rendered using the
approved German phrase) and one flag: `requires_legal_review`, with the
fictional "EU-DE Advertising Disclosure Rule (ADR-7)" reason shown inline.
Point out the info box above the drafts: translation drafts do not replace
legal, regulatory, or local-market review -- that flag is a pointer to a
human step, not a completed one.

**0:50 -- Inspect the Korean draft.**
Scroll to Korean. It carries *two* flags at once --
`requires_legal_review` and `requires_cultural_review` -- from the
fictional "KEC-15" disclosure rule and the honorific-register policy. This
shows the market-rules engine isn't just a single boolean per market.

**1:00 -- Play reviewer.**
In section 3, "Native reviewer panel," find the German draft. Type a note
("Confirmed disclosure line is present") and click **Approve**. Find the
Korean draft, type a note ("Honorific register needs a second pass"), and
click **Request revision** -- note this is a third, distinct button from
Reject, and the draft moves to "Reviewed drafts" labeled
`revision_requested`, not `rejected`.

**1:10 -- Resubmit.**
Next to the Korean draft in "Reviewed drafts," click **Resubmit for
review** -- it moves back to the pending queue with a fresh `submitted`
audit-log entry, modeling the real revise-and-resubmit loop.

**1:20 -- Audit trail.**
Scroll to section 4. The table shows every transition so far: `submitted`
for all 6 drafts, `approved` for German, `revision_requested` for Korean,
then a second `submitted` for Korean after resubmission -- each with a
timestamp.

**1:30 -- Reset.**
Click "Reset state" at the top. The drafts and the audit-trail table both
clear back to empty, ready for the next walkthrough.

---

That's the full loop: generate -> glossary/market-rule check -> human
review (approve / reject / request revision) -> audit trail -> reset.
