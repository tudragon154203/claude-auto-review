from __future__ import annotations

import re

from claude_auto_review.state.reviews.review_text import extract_review_findings_text

_FINDING_HEADING = re.compile(r"^###\s+(\d+\.|\[)")
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
_CONTRADICTION_RE = re.compile(
    r"\b(?:but|however|except|although|though)\b",
    re.IGNORECASE,
)
_PUNCTUATION_CHARS = ".,;:-—"
_INDENTED_FIELD_RE = re.compile(r"^\s+(Severity|Verdict|Reason|Rule|Location|Rationale|Suggestion):\s*", re.IGNORECASE)


def _is_no_findings_line(line: str) -> bool:
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


def _has_canonical_confirmed_finding(findings: str) -> bool:
    current_verdict = None
    current_lines: list[str] = []
    has_canonical_fields = False

    _ISSUE_INDICATOR_RE = re.compile(
        r"\b(?:found|vulnerability|injection|exploit|bug|defect|issue|error|flaw|race|overflow|XSS|CSRF)\b",
        re.IGNORECASE,
    )

    def block_is_finding(verdict: str | None, lines: list[str], fields: bool) -> bool:
        if verdict is None:
            return False
        if verdict == "skipped":
            if not lines:
                return False
            combined = " ".join(lines)
            skip_match = _SKIP_NO_CONTENT_RE.search(combined)
            if skip_match:
                remainder = combined[skip_match.end():]
                if _CONTRADICTION_RE.search(remainder):
                    return bool(_ISSUE_INDICATOR_RE.search(remainder))
                return False
            return bool(_ISSUE_INDICATOR_RE.search(combined))
        if fields:
            return True
        return not all(_is_no_findings_line(line) for line in lines if line.strip())

    for line in findings.splitlines():
        stripped = line.strip()
        bullet = _FINDING_BULLET_RE.match(stripped)
        if bullet:
            if block_is_finding(current_verdict, current_lines, has_canonical_fields):
                return True
            current_verdict = bullet.group(1).lower()
            current_lines = [stripped[bullet.end():].strip()]
            has_canonical_fields = False
            continue
        if current_verdict is not None:
            if _INDENTED_FIELD_RE.match(line):
                has_canonical_fields = True
            elif stripped:
                current_lines.append(stripped)
    return block_is_finding(current_verdict, current_lines, has_canonical_fields)


def has_review_findings(content: str | None) -> bool:
    findings = extract_review_findings_text(content)
    if not findings:
        return False
    if _has_canonical_confirmed_finding(findings):
        return True

    lines = findings.splitlines()
    if any(_FINDING_HEADING.match(line.strip()) for line in lines if line.strip()):
        return True

    meaningful_lines = []
    skipping_notes = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == "```":
            continue
        if _FINDING_BULLET_RE.match(stripped) or _INDENTED_FIELD_RE.match(line):
            continue
        if stripped.lower().startswith("**notes:**") or stripped.lower().startswith("notes:"):
            skipping_notes = True
            continue
        if skipping_notes:
            if stripped.startswith("## ") or stripped.startswith("### "):
                skipping_notes = False
            else:
                continue
        meaningful_lines.append(line)
    if not meaningful_lines:
        return False
    first = meaningful_lines[0]
    first_lower = first.strip().casefold()
    for prefix in _DEFINITIVE_NO_FINDINGS_PREFIXES:
        if first_lower.startswith(prefix) and _is_no_findings_line(first):
            if not any(_CONTRADICTION_RE.search(line) for line in meaningful_lines[1:]):
                return False
            break
    return not all(_is_no_findings_line(line) for line in meaningful_lines)
