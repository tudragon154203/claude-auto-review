from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from claude_auto_review.config.models import (
    DEFAULT_MINIMUM_BLOCKING_SEVERITY,
    MINIMUM_BLOCKING_SEVERITIES,
)
from claude_auto_review.runtime.events import log_event


def extract_review_verdict_text(content: str | None) -> str | None:
    if not content:
        return None
    if "## Verdict" in content:
        verdict_block = content.split("## Verdict", 1)[1]
        for line in verdict_block.splitlines():
            verdict = line.strip()
            if verdict:
                return verdict
    if "## Findings" not in content:
        return None
    findings_block = content.split("## Findings", 1)[1]
    for line in findings_block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^(clean\b|confirmed\s*\(\s*clean\s*\))", line, re.IGNORECASE):
            return line
    return None


def extract_review_findings_text(content: str | None) -> str | None:
    if not content or "## Findings" not in content:
        return None
    findings_block = content.split("## Findings", 1)[1]
    if "## Verdict" in findings_block:
        findings_block = findings_block.split("## Verdict", 1)[0]
    findings = findings_block.strip()
    return findings or None


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
_FINDING_HEADING_RE = re.compile(r"^\s*###\s+(.+?)\s*$")
_CONFIRMED_PREFIX = re.compile(r"^confirmed(?:\b|\s|$)", re.IGNORECASE)
_SKIPPED_PREFIX = re.compile(r"^skipped(?:\b|\s|$)", re.IGNORECASE)


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
    # A structured ### finding heading always means there are findings.
    # An explicit "no findings" negation is only trusted when no heading appears at all.
    if any(_FINDING_HEADING.match(l.strip()) for l in lines if l.strip()):
        return True
    return not all(_is_no_findings_line(line) for line in lines if line.strip())


def _replace_verdict_text(content: str, new_verdict: str) -> str:
    if "## Verdict" not in content:
        return content
    # Preserve the exact whitespace sequence between ## Verdict and the first
    # content line. The original code reconstructed with a hardcoded "\n", which
    # would alter output if the heading was followed by \r\n or extra blank lines.
    before, after = content.split("## Verdict", 1)
    lines = after.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip():
            lines[i] = new_verdict + ("\r\n" if line.endswith("\r\n") else "\n")
            break
    else:
        lines.append(new_verdict + "\n")
    return before + "## Verdict" + "".join(lines)


def normalize_review_verdict_content(content: str | None) -> str | None:
    if not content:
        return content
    if "## Verdict" not in content:
        return content
    verdict = extract_review_verdict_text(content)
    if not verdict or not is_review_complete_verdict(verdict):
        return content
    findings_exist = has_review_findings(content)

    if is_review_clean_verdict(verdict):
        if findings_exist:
            rewritten = _replace_verdict_text(
                content,
                "Findings present. Claude must address all findings before stopping.",
            )
            if rewritten != content:
                log_event(Path.cwd(), "review_verdict_normalized", original_verdict=verdict, normalized_verdict="Findings present. Claude must address all findings before stopping.")
            return rewritten
        return content

    if not findings_exist:
        rewritten = _replace_verdict_text(content, "Clean - no issues found. Claude may stop.")
        if rewritten != content:
            log_event(Path.cwd(), "review_verdict_normalized", original_verdict=verdict, normalized_verdict="Clean - no issues found. Claude may stop.")
        return rewritten

    return content


def is_placeholder_review_content(content: str | None) -> bool:
    if not content:
        return True
    text = content.strip()
    if not text:
        return True
    placeholder_markers = (
        "No findings yet. This file is a placeholder until Claude completes the review.",
        "Pending. Claude must complete this review",
        "## Verdict\n\nPending.",
    )
    return any(marker in text for marker in placeholder_markers)


def is_completed_review_content(content: str | None) -> bool:
    return not is_placeholder_review_content(content)


def get_review_verdict_text(review_path: str | Path) -> str | None:
    path = Path(review_path)
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8", errors="replace")
    return extract_review_verdict_text(content)


# Patterns that unambiguously signal a completed review verdict.
# Negative patterns (incomplete/pending) are checked first in is_review_complete_verdict.
_COMPLETE_VERDICT = re.compile(
    r"^(?:"
    r"clean\b"
    r"|confirmed\s*(?:\(\s*clean\s*\))?"
    r"|not\s+clean\b"
    r"|\d+\s+issues?\b"
    r"|all\s+(?:(?:fixes|issues?)\s+)?(?:applied|addressed)\b"
    r"|findings?\s+present\b"
    r"|has\s+findings?\b"
    r"|issue(?:s)?\s+found\b"
    r")",
    re.IGNORECASE,
)


def is_review_complete_verdict(verdict: str | None) -> bool:
    if not verdict:
        return False
    verdict = verdict.strip().lower()
    if verdict in ("pending", "pending."):
        return False
    return bool(_COMPLETE_VERDICT.match(verdict))


def is_review_clean_verdict(verdict: str | None) -> bool:
    if not verdict:
        return False
    verdict = verdict.strip().lower()
    if verdict.startswith("not clean"):
        return False
    if verdict.startswith("clean"):
        return True
    return bool(re.match(r"^confirmed\s*\(\s*clean\s*\)(?:\s|$|[-:])", verdict))


def is_review_clean_content(content: str | None) -> bool:
    verdict = extract_review_verdict_text(content)
    if not is_review_clean_verdict(verdict):
        return False
    return not has_review_findings(content)


def is_review_complete(review_path: str | Path) -> bool:
    return is_review_complete_verdict(get_review_verdict_text(review_path))


def is_review_clean(review_path: str | Path) -> bool:
    path = Path(review_path)
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8", errors="replace")
    return is_review_clean_content(content)
