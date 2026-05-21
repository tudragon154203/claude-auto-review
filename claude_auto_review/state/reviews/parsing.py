from __future__ import annotations

import re
from dataclasses import dataclass

from claude_auto_review.config.models import MINIMUM_BLOCKING_SEVERITIES
from claude_auto_review.state.reviews.review_text import extract_review_findings_text

_FINDING_HEADING = re.compile(r"^###\s+(\d+\.|\[)")
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
        is_start = stripped.startswith("###")
        if current is None and _FINDING_FIELD_RE.match(stripped):
            lower = stripped.lower()
            if lower.startswith(("severity:", "**severity:", "- severity:", "- **severity:")):
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
