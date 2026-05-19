from __future__ import annotations

import re
from pathlib import Path

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
    "none",
    "clean",
)
_STRICT_NO_FINDINGS_PREFIXES = {"none", "clean"}
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
    for prefix in _NO_FINDINGS_PREFIXES:
        if not lowered.startswith(prefix):
            continue

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
    return not any(_is_no_findings_line(l) for l in lines if l.strip())


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
