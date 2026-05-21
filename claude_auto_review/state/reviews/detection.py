from __future__ import annotations

import re

from claude_auto_review.state.reviews.review_text import extract_review_findings_text

_FINDING_HEADING = re.compile(r"^###\s+(\d+\.|\[)")
_NO_FINDINGS_PREFIXES = (
    "no semantic issues",
    "no semantic issue",
    "no semantic bugs",
    "no semantic bug",
    "no semantic concerns",
    "no semantic concern",
    "no semantic problems",
    "no semantic problem",
    "no semantic violations",
    "no semantic violation",
    "no findings",
    "no issues",
    "no bugs",
    "no concerns",
    "no problems",
    "no violations",
    "completed review from",
    "all code follows project conventions",
    "none",
    "clean",
)
_STRICT_NO_FINDINGS_PREFIXES = {"none", "clean"}
_ALWAYS_NO_FINDINGS_PREFIXES = {"completed review from"}
_NO_FINDINGS_VERB_RE = re.compile(
    r"\b(?:found|identified|detected|yet)\b",
    re.IGNORECASE,
)
_CONTRADICTION_RE = re.compile(
    r"\b(?:but|however|except|although|though)\b",
    re.IGNORECASE,
)
_PUNCTUATION_CHARS = ".,;:-—"



def _is_no_findings_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    lowered = text.casefold()
    # Only treat Notes as no-findings when it explicitly states no issues were found
    if lowered.startswith("**note:**") or lowered.startswith("note:"):
        if "no project rules file found" in lowered or "basic semantic review only" in lowered:
            return True
        # Don't treat generic Notes sections as no-findings markers
        return False
    for prefix in _NO_FINDINGS_PREFIXES:
        if not lowered.startswith(prefix):
            continue

        if prefix in _ALWAYS_NO_FINDINGS_PREFIXES:
            return True

        remainder = text[len(prefix):].lstrip()
        if not remainder:
            return True

        if prefix in _STRICT_NO_FINDINGS_PREFIXES:
            return remainder[0] in _PUNCTUATION_CHARS and not _CONTRADICTION_RE.search(remainder)

        if _CONTRADICTION_RE.search(remainder):
            return False

        if remainder[0] in _PUNCTUATION_CHARS:
            return True

        if _NO_FINDINGS_VERB_RE.search(remainder):
            return True

        return False
    return False



def has_review_findings(content: str | None) -> bool:
    findings = extract_review_findings_text(content)
    if not findings:
        return False
    lines = findings.splitlines()
    if any(_FINDING_HEADING.match(l.strip()) for l in lines if l.strip()):
        return True
    meaningful_lines = []
    skipping_notes = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("**notes:**") or stripped.lower().startswith("notes:"):
            skipping_notes = True
            continue
        if skipping_notes:
            # Break out on both section headers (##) and finding headings (###)
            if stripped.startswith("## ") or stripped.startswith("### "):
                skipping_notes = False
            else:
                continue
        meaningful_lines.append(line)
    if not meaningful_lines:
        return False
    return not all(_is_no_findings_line(line) for line in meaningful_lines)
