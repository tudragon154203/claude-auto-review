from __future__ import annotations

import re
from dataclasses import dataclass

from claude_auto_review.config.models import (
    DEFAULT_MINIMUM_BLOCKING_SEVERITY,
    MINIMUM_BLOCKING_SEVERITIES,
)
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

_FINDING_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?\*{0,2}(Severity|Verdict):\*{0,2}\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class ReviewFinding:
    severity: str | None
    verdict: str | None
    raw_text: str


def _normalize_severity(value: str | None) -> str | None:
    if value is None:
        return None
    severity = value.strip().lower()
    return severity if severity in MINIMUM_BLOCKING_SEVERITIES else None


def _severity_rank(value: str) -> int | None:
    normalized = _normalize_severity(value)
    if normalized is None:
        return None
    return {
        "info": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }[normalized]


def _extract_heading_severity(line: str) -> str | None:
    text = line.strip()
    if not text.startswith("###"):
        return None
    text = text[3:].strip()
    text = re.sub(r"^\d+[.)]?\s*", "", text)
    match = re.match(r"^\[(?P<severity>[^\]]+)\]", text)
    if match:
        return _normalize_severity(match.group("severity"))
    first_token = text.split(None, 1)[0] if text else ""
    return _normalize_severity(first_token.strip("[]:-")) if first_token else None


def _parse_finding_block(block: str) -> ReviewFinding:
    severity = None
    verdict = None
    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    if lines:
        severity = _extract_heading_severity(lines[0])
    field_matches = _FINDING_FIELD_RE.findall(block)
    for field_name, field_value in field_matches:
        normalized_field = field_name.lower()
        if normalized_field == "severity" and severity is None:
            severity = _normalize_severity(field_value)
        elif normalized_field == "verdict" and verdict is None:
            verdict = field_value.strip()
    return ReviewFinding(severity=severity, verdict=verdict, raw_text=block)


def parse_review_findings(content: str | None) -> list[ReviewFinding]:
    findings_text = extract_review_findings_text(content)
    if not findings_text:
        return []

    blocks: list[str] = []
    current: list[str] | None = None
    for line in findings_text.splitlines():
        stripped = line.strip()
        is_start = stripped.startswith("###") or stripped.startswith("- **Severity:**")
        if current is None and _FINDING_FIELD_RE.match(stripped) and stripped.lower().startswith(("severity:", "**severity:**", "- **severity:**")):
            is_start = True
        if is_start:
            if current is not None:
                block = "\n".join(current).strip()
                if block:
                    blocks.append(block)
            current = [line]
            continue
        if current is not None:
            current.append(line)

    if current is not None:
        block = "\n".join(current).strip()
        if block:
            blocks.append(block)

    return [_parse_finding_block(block) for block in blocks]


def _is_no_findings_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    lowered = text.casefold()
    if lowered.startswith("**note:**") or lowered.startswith("note:"):
        if "no project rules file found" in lowered or "basic semantic review only" in lowered:
            return True
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
    meaningful_lines = [line for line in lines if line.strip()]
    if not meaningful_lines:
        return False
    return not all(_is_no_findings_line(line) for line in meaningful_lines)


def has_blocking_review_findings(content: str | None, minimum_blocking_severity: str = DEFAULT_MINIMUM_BLOCKING_SEVERITY) -> bool:
    threshold = _severity_rank(minimum_blocking_severity) if minimum_blocking_severity else None
    if threshold is None:
        threshold = _severity_rank(DEFAULT_MINIMUM_BLOCKING_SEVERITY)

    findings = parse_review_findings(content)
    if not findings:
        return has_review_findings(content)

    for finding in findings:
        verdict = (finding.verdict or "").strip().lower()
        if verdict.startswith("skipped"):
            continue
        if not verdict.startswith("confirmed"):
            return True
        if finding.severity is None:
            return True
        severity_rank = _severity_rank(finding.severity)
        if severity_rank is None or severity_rank >= threshold:
            return True
    return False
