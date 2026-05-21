from __future__ import annotations

from pathlib import Path

from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.reviews.completion import (
    is_review_clean_verdict,
    is_review_complete_verdict,
)
from claude_auto_review.state.reviews.findings import has_review_findings
from claude_auto_review.state.reviews.review_text import extract_review_verdict_text


def _replace_verdict_text(content: str, new_verdict: str) -> str:
    if "## Verdict" not in content:
        return content
    before, after = content.split("## Verdict", 1)
    lines = after.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip():
            lines[i] = new_verdict + ("\r\n" if line.endswith("\r\n") else "\n")
            break
    else:
        lines.append(new_verdict + "\n")
    return before + "## Verdict" + "".join(lines)


def normalize_review_verdict_content(content: str | None, client_id: str | None = None) -> str | None:
    """
    Normalize review verdict text to ensure consistent blocking behavior.

    Args:
        content: The review markdown content to normalize.
        client_id: Optional client ID for logging. Pass None when client context
            is unavailable (e.g., called outside stop hook flow). When None,
            log_event will omit clientId from the event entry.
    """
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
                log_event(Path.cwd(), "review_verdict_normalized", client_id=client_id, original_verdict=verdict, normalized_verdict="Findings present. Claude must address all findings before stopping.")
            return rewritten
        return content

    if not findings_exist:
        rewritten = _replace_verdict_text(content, "Clean - no issues found. Claude may stop.")
        if rewritten != content:
            log_event(Path.cwd(), "review_verdict_normalized", client_id=client_id, original_verdict=verdict, normalized_verdict="Clean - no issues found. Claude may stop.")
        return rewritten

    return content
