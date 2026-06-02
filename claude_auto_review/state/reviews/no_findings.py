"""Detect 'no findings' lines in review output."""
from __future__ import annotations

import re

_FINDING_BULLET_RE = re.compile(r"^[-*]\s*(confirmed|skipped):\s*", re.IGNORECASE)
_SKIP_NO_CONTENT_RE = re.compile(
    r"\b(?:"
    r"does\s+not\s+exist"
    r"|is\s+not\s+(?:found|present|available)\s+in\s+(?:the\s+)?(?:scope|snapshot|workspace)"
    r"|not\s+(?:found|present|available)\s+in\s+(?:the\s+)?(?:scope|snapshot|workspace)"
    r"|not\s+in\s+(?:scope|snapshot|workspace)"
    r"|referenced\s+but\s+does\s+not\s+exist\s+in\s+(?:the\s+)?(?:scope|snapshot|workspace)"
    r")\b",
    re.IGNORECASE,
)
_CONTRADICTION_RE = re.compile(
    r"\b(?:but|however|except|although|though)\b",
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
    "no defects",
    "no confirmed findings",
    "completed review from",
    "all code follows project conventions",
    "none",
    "clean",
)
_STRICT_NO_FINDINGS_PREFIXES = {"none", "clean"}
_UNQUALIFIED_NO_FINDINGS_PREFIXES = {"completed review from"}
_DEFINITIVE_NO_FINDINGS_PREFIXES = _STRICT_NO_FINDINGS_PREFIXES | _UNQUALIFIED_NO_FINDINGS_PREFIXES
_NO_FINDINGS_VERB_RE = re.compile(
    r"\b(?:found|identified|detected|yet|remain|remains|were\s+found|were\s+identified)\b",
    re.IGNORECASE,
)
_PUNCTUATION_CHARS = ".,;:-—"


def is_no_findings_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    lowered = text.casefold()
    if lowered == "none.":
        return True
    if lowered.startswith("**note:**") or lowered.startswith("note:"):
        if "no project rules file found" in lowered or "basic semantic review only" in lowered:
            return not _CONTRADICTION_RE.search(lowered)
        return False
    m = _FINDING_BULLET_RE.match(text)
    if m:
        remainder = text[m.end():].strip()
        if m.group(1).lower() == "skipped":
            if not remainder:
                return True
            no_content_match = _SKIP_NO_CONTENT_RE.search(remainder)
            if not no_content_match:
                return False
            return not bool(_CONTRADICTION_RE.search(remainder, no_content_match.end()))
        return bool(remainder) and is_no_findings_line(remainder)
    for prefix in _NO_FINDINGS_PREFIXES:
        if not lowered.startswith(prefix):
            continue
        if prefix in _UNQUALIFIED_NO_FINDINGS_PREFIXES:
            remainder = text[len(prefix):].lstrip()
            if not remainder:
                return True
            return not _CONTRADICTION_RE.search(remainder)
        remainder = text[len(prefix):].lstrip()
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
