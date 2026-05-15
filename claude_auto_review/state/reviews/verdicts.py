from __future__ import annotations

import re
from pathlib import Path


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


def has_review_findings(content: str | None) -> bool:
    findings = extract_review_findings_text(content)
    if not findings:
        return False
    return not re.match(r"^(none\b|no findings\b|no issues\b|clean\b)", findings.strip(), re.IGNORECASE)


def normalize_review_verdict_content(content: str | None) -> str | None:
    if not content:
        return content
    verdict = extract_review_verdict_text(content)
    if not is_review_clean_verdict(verdict):
        return content
    if not has_review_findings(content):
        return content
    if "## Verdict" not in content:
        return content

    stricter_verdict = "Findings present. Claude must address all findings before stopping."
    before, after = content.split("## Verdict", 1)
    lines = after.splitlines()
    replaced = False
    new_lines: list[str] = []
    for line in lines:
        if replaced:
            new_lines.append(line)
            continue
        if line.strip():
            new_lines.append(line.replace(line.strip(), stricter_verdict, 1))
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(stricter_verdict)
    return before + "## Verdict\n" + "\n".join(new_lines)


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


def is_review_complete_verdict(verdict: str | None) -> bool:
    if not verdict:
        return False
    return verdict.strip().lower() not in ("pending", "pending.")


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
