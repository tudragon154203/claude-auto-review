from __future__ import annotations

import re
from dataclasses import dataclass

from claude_auto_review.config.severity import MINIMUM_BLOCKING_SEVERITIES
from claude_auto_review.state.reviews.review_text import extract_review_findings_text

_FINDING_HEADING = re.compile(r"^###\s+(\d+\.|\[)")
_FINDING_INLINE_SEVERITY_RE = re.compile(
    r"^\d+[.)]?\s*\*{1,2}\s*(Confirmed|Skipped)\s*-\s*(Info|Low|Medium|High|Critical)(?:\*\*|[:\s]|$)",
    re.IGNORECASE,
)
_FINDING_INLINE_NO_SEV_RE = re.compile(
    r"^\d+[.)]?\s*\*{1,2}\s*(Confirmed|Skipped)\s*-\s+",
    re.IGNORECASE,
)
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


def _extract_heading_severity(line: str) -> tuple[str | None, str | None]:
    """Extract (severity, verdict) from a finding heading line.

    Handles three formats:
      ### 1. [Confirmed - Critical] ...     # explicit field in brackets
      ### 1. Critical - ...                # bare severity token
      1. **Confirmed - Critical** ...      # inline badge (codex/reviewer format)
    Returns (severity, verdict) so verdict can be inferred from the heading.
    """
    text = line.strip()
    # Inline badge: "1. **Confirmed - Critical**" or "1. **Confirmed - Critical - description**"
    inline_match = _FINDING_INLINE_SEVERITY_RE.match(text)
    if inline_match:
        verdict_raw = inline_match.group(1).strip().lower()
        severity_raw = inline_match.group(2).strip()
        severity = _normalize_severity(severity_raw)
        verdict = verdict_raw if verdict_raw in {"confirmed", "skipped"} else None
        return severity, verdict
    if not text.startswith("###"):
        return None, None
    text = text[3:].strip()
    text = re.sub(r"^\d+[.)]?\s*", "", text)
    match = re.match(r"^\[(?P<label>[^\]]+)\]", text)
    if match:
        label = match.group("label")
        if "-" in label:
            verdict_raw, severity_raw = [part.strip() for part in label.split("-", 1)]
            severity = _normalize_severity(severity_raw)
            verdict = verdict_raw.lower()
            if severity is not None and verdict in {"confirmed", "skipped"}:
                return severity, verdict
        return _normalize_severity(label.strip()), None
    first_token = text.split(None, 1)[0] if text else ""
    return _normalize_severity(first_token.strip("[]:-")) if first_token else None, None


def _parse_finding_block(block: str) -> ReviewFinding:
    severity = None
    verdict = None
    lines = [line.rstrip() for line in block.splitlines() if line.strip()]
    if lines:
        heading_severity, heading_verdict = _extract_heading_severity(lines[0])
        if heading_severity is not None:
            severity = heading_severity
        if heading_verdict is not None:
            verdict = heading_verdict
    field_matches = _FINDING_FIELD_RE.findall(block)
    for field_name, field_value in field_matches:
        normalized_field = field_name.lower()
        if normalized_field == "severity" and severity is None:
            severity = _normalize_severity(field_value)
        elif normalized_field == "verdict":
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
        is_start = stripped.startswith("###") or _FINDING_INLINE_SEVERITY_RE.match(stripped) or _FINDING_INLINE_NO_SEV_RE.match(stripped)
        if current is None and _FINDING_FIELD_RE.match(stripped):
            lower = stripped.lower()
            if lower.startswith(("severity:", "**severity:", "- severity:", "- **severity:")):
                field_match = _FINDING_FIELD_RE.match(stripped)
                if field_match and _normalize_severity(field_match.group(2)) is not None:
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

    results = []
    for block in blocks:
        finding = _parse_finding_block(block)
        first_line = block.splitlines()[0].strip() if block else ""
        no_sev_match = _FINDING_INLINE_NO_SEV_RE.match(first_line)
        if no_sev_match and not _FINDING_INLINE_SEVERITY_RE.match(first_line):
            if finding.verdict is None and not _FINDING_FIELD_RE.search(block):
                continue
        results.append(finding)
    return results
