from __future__ import annotations

import re
from dataclasses import dataclass

from claude_auto_review.config.severity import MINIMUM_BLOCKING_SEVERITIES
from claude_auto_review.state.reviews.review_text import extract_review_findings_text

_UNRECOGNIZED_SEVERITY = "<unrecognized>"

_FINDING_BULLET_RE = re.compile(r"^[-*]\s*(Confirmed|Skipped):\s*(.*)$", re.IGNORECASE)
_LEGACY_FINDING_START_RE = re.compile(r"^###\s+|^\d+[.)]?\s*\*{1,2}\s*(?:Confirmed|Skipped)\s*-\s*", re.IGNORECASE)

_LEGACY_INLINE_SEVERITY_RE = re.compile(
    r"^\d+[.)]?\s*\*{1,2}\s*(Confirmed|Skipped)\s*-\s*(Info|Low|Medium|High|Critical)(?:\*\*|[:\s]|$)",
    re.IGNORECASE,
)
_FINDING_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?\*{0,2}(Severity|Verdict):\*{0,2}\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_CANONICAL_FIELD_RE = re.compile(r"^\s+(Severity|Verdict|Reason|Rule|Location|Rationale|Suggestion):\s*(.+?)\s*$", re.IGNORECASE)


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


def _legacy_heading_severity(line: str) -> tuple[str | None, str | None]:
    text = line.strip()
    inline_match = _LEGACY_INLINE_SEVERITY_RE.match(text)
    if inline_match:
        return _normalize_severity(inline_match.group(2)), inline_match.group(1).lower()
    if not text.startswith("###"):
        return None, None
    text = re.sub(r"^###\s+(?:\d+[.)]?\s*)?", "", text)
    bracket_match = re.match(r"^\[(?P<label>[^\]]+)\]", text)
    if bracket_match:
        label = bracket_match.group("label")
        if "-" in label:
            verdict_raw, severity_raw = [part.strip() for part in label.split("-", 1)]
            severity = _normalize_severity(severity_raw)
            verdict = verdict_raw.lower()
            if severity is not None and verdict in {"confirmed", "skipped"}:
                return severity, verdict
        severity = _normalize_severity(label)
        if severity is not None:
            return severity, None
        if " " not in label.strip() and "-" not in label.strip():
            return _UNRECOGNIZED_SEVERITY, None
    return None, None


def _extract_heading_severity(line: str) -> tuple[str | None, str | None]:
    return _legacy_heading_severity(line)


def _parse_finding_block(block: str) -> ReviewFinding:
    severity = None
    verdict = None
    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    if lines:
        bullet_match = _FINDING_BULLET_RE.match(lines[0].strip())
        if bullet_match:
            verdict = bullet_match.group(1).lower()
        else:
            severity, verdict = _legacy_heading_severity(lines[0])

    for line in lines[1:] if verdict in {"confirmed", "skipped"} else lines:
        canonical_match = _CANONICAL_FIELD_RE.match(line)
        if not canonical_match:
            continue
        field_name = canonical_match.group(1).lower()
        field_value = canonical_match.group(2)
        if field_name == "severity" and severity in (None, _UNRECOGNIZED_SEVERITY):
            normalized = _normalize_severity(field_value)
            severity = normalized if normalized is not None else severity or _UNRECOGNIZED_SEVERITY
        elif field_name == "verdict":
            verdict = field_value.strip()

    for field_name, field_value in _FINDING_FIELD_RE.findall(block):
        normalized_field = field_name.lower()
        if normalized_field == "severity" and severity in (None, _UNRECOGNIZED_SEVERITY):
            severity = _normalize_severity(field_value) or _UNRECOGNIZED_SEVERITY
        elif normalized_field == "verdict" and verdict is None:
            verdict = field_value.strip()
    return ReviewFinding(severity=severity, verdict=verdict, raw_text=block)


def _split_finding_blocks(findings_text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] | None = None
    for line in findings_text.splitlines():
        stripped = line.strip()
        is_start = bool(_FINDING_BULLET_RE.match(stripped) or _LEGACY_FINDING_START_RE.match(stripped))
        if is_start:
            if current is not None:
                block = "\n".join(current).strip()
                if block:
                    blocks.append(block)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        block = "\n".join(current).strip()
        if block:
            blocks.append(block)
    return blocks


def parse_review_findings(content: str | None) -> list[ReviewFinding]:
    findings_text = extract_review_findings_text(content)
    if not findings_text:
        return []

    results = []
    for block in _split_finding_blocks(findings_text):
        finding = _parse_finding_block(block)
        first_line = block.splitlines()[0].strip() if block else ""
        has_fields = bool(_FINDING_FIELD_RE.search(block) or _CANONICAL_FIELD_RE.search(block))
        if first_line.startswith("###") and finding.severity is None and finding.verdict is None and not has_fields:
            continue
        if finding.verdict is None and finding.severity is None:
            continue
        results.append(finding)
    return results
