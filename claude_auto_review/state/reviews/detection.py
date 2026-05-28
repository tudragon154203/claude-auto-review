from __future__ import annotations

import re

from claude_auto_review.state.reviews.review_text import extract_review_findings_text

_FINDING_HEADING = re.compile(r"^###\s+(\d+\.|\[)")
_BULLET_VERDICT_RE = re.compile(r"^[-*]\s*(confirmed|skipped):\s*", re.IGNORECASE)
_SKIP_NO_CONTENT_RE = re.compile(
    r"\b(?:"
    r"does\s+not\s+exist"
    r"|not\s+(?:found|present|available)\s+in\s+(?:the\s+)?(?:scope|snapshot|workspace)"
    r"|not\s+in\s+(?:scope|snapshot|workspace)"
    r")\b",
    re.IGNORECASE,
)
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
    "no semantic,",
    "no findings",
    "no issues",
    "no bugs",
    "no concerns",
    "no problems",
    "no violations",
    "no confirmed findings",
    "completed review from",
    "all code follows project conventions",
    "none",
    "clean",
)
_STRICT_NO_FINDINGS_PREFIXES = {"none", "clean"}
# Prefixes that match as no-findings without requiring punctuation or a verb tail.
# Contradiction words (but/however/…) in the remainder still override to False.
_UNQUALIFIED_NO_FINDINGS_PREFIXES = {"completed review from"}
_DEFINITIVE_NO_FINDINGS_PREFIXES = _STRICT_NO_FINDINGS_PREFIXES | _UNQUALIFIED_NO_FINDINGS_PREFIXES
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
        return "no project rules file found" in lowered or "basic semantic review only" in lowered
    # Handle bullet-style "- Confirmed: ..." and "- Skipped: ..." formats.
    # Skipped items never block; for Confirmed bullets, check the remainder.
    m = _BULLET_VERDICT_RE.match(text)
    if m:
        remainder = text[m.end():].strip()
        if m.group(1).lower() == "skipped":
            if not remainder:
                return True
            no_content_match = _SKIP_NO_CONTENT_RE.search(remainder)
            if not no_content_match:
                return False
            return not bool(_CONTRADICTION_RE.search(remainder, no_content_match.end()))
        return bool(remainder) and _is_no_findings_line(remainder)
    for prefix in _NO_FINDINGS_PREFIXES:
        if not lowered.startswith(prefix):
            continue

        if prefix in _UNQUALIFIED_NO_FINDINGS_PREFIXES:
            remainder = text[len(prefix) :].lstrip()
            if not remainder:
                return True
            return not _CONTRADICTION_RE.search(remainder)

        remainder = text[len(prefix) :].lstrip()
        if not remainder:
            return True

        if prefix in _STRICT_NO_FINDINGS_PREFIXES:
            return remainder[0] in _PUNCTUATION_CHARS and not _CONTRADICTION_RE.search(remainder)

        if _CONTRADICTION_RE.search(remainder):
            return False

        if remainder[0] in _PUNCTUATION_CHARS:
            return True

        return bool(_NO_FINDINGS_VERB_RE.search(remainder))
    return False


def has_review_findings(content: str | None) -> bool:
    findings = extract_review_findings_text(content)
    if not findings:
        return False
    lines = findings.splitlines()
    if any(_FINDING_HEADING.match(line.strip()) for line in lines if line.strip()):
        return True
    meaningful_lines = []
    skipping_notes = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == "```":
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
    # If the first meaningful line is a definitive "no findings" marker
    # (e.g., "None." or "Clean.") with no contradictions anywhere in the
    # section, short-circuit to avoid re-checking every line.
    # ###-prefixed findings were already caught by _FINDING_HEADING above.
    first = meaningful_lines[0]
    first_lower = first.strip().casefold()
    for prefix in _DEFINITIVE_NO_FINDINGS_PREFIXES:
        if first_lower.startswith(prefix) and _is_no_findings_line(first):
            if not any(_CONTRADICTION_RE.search(line) for line in meaningful_lines[1:]):
                return False
            break
    return not all(_is_no_findings_line(line) for line in meaningful_lines)
