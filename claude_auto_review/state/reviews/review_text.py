from __future__ import annotations

import re
from pathlib import Path

# Matches a single fenced code block: an opening ``` line through the
# corresponding closing ``` line.  Two forms are supported:
#   - fenced block   : "^```[\s\S]*?^```"
#   - inline          : "^`[^`\s].*?^`"
# Both use lazy quantifiers so an unclosed fence only reaches the next
# fence start (or EOF if none is found), never swallowing real findings.
_FENCED_BLOCK_RE = re.compile(
    r"^```[\s\S]*?^```"
    r"|^`[^`\s].*?^`(?![^`]*`|$)",
    re.MULTILINE,
)


def _strip_code_fences(text: str) -> str:
    return _FENCED_BLOCK_RE.sub("", text)


def extract_review_verdict_text(content: str | None) -> str | None:
    if not content:
        return None
    # Strip code fences so ## Findings / ## Verdict inside snippets are ignored.
    text = _strip_code_fences(content)
    if "## Verdict" in text:
        verdict_block = text.split("## Verdict", 1)[1]
        for line in verdict_block.splitlines():
            verdict = line.strip()
            if verdict:
                return verdict
    if "## Findings" not in text:
        return None
    findings_block = text.split("## Findings", 1)[1]
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
    # Strip code fences so ## Findings / ## Verdict inside snippets are ignored.
    text = _strip_code_fences(content)
    if "## Findings" not in text:
        return None
    findings_block = text.split("## Findings", 1)[1]
    if "## Verdict" in findings_block:
        findings_block = findings_block.split("## Verdict", 1)[0]
    findings = findings_block.strip()
    return findings or None


def get_review_verdict_text(review_path: str | Path) -> str | None:
    path = Path(review_path)
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8", errors="replace")
    return extract_review_verdict_text(content)
