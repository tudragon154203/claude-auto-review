"""Detect whether review output contains actionable findings."""
from __future__ import annotations

import re

from claude_auto_review.state.reviews.no_findings import (
    _CONTRADICTION_RE,
    _FINDING_BULLET_RE,
    _SKIP_NO_CONTENT_RE,
    is_no_findings_line,
)
from claude_auto_review.state.reviews.review_text import extract_review_findings_text

_FINDING_HEADING = re.compile(r"^###\s+(\d+\.|\[)")
_INDENTED_FIELD_RE = re.compile(r"^\s+(Severity|Verdict|Reason|Rule|Location|Rationale|Suggestion):\s*", re.IGNORECASE)

_DEFINITIVE_NO_FINDINGS_PREFIXES = {"none", "clean", "completed review from"}


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
        return not all(is_no_findings_line(line) for line in lines if line.strip())

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
        if first_lower.startswith(prefix) and is_no_findings_line(first):
            if not any(_CONTRADICTION_RE.search(line) for line in meaningful_lines[1:]):
                return False
            break
    return not all(is_no_findings_line(line) for line in meaningful_lines)
