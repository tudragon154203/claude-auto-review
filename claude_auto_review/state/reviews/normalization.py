from __future__ import annotations

from pathlib import Path

from claude_auto_review.config.models import DEFAULT_MINIMUM_BLOCKING_SEVERITY
from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.reviews.blocking import has_blocking_review_findings
from claude_auto_review.state.reviews.completion import (
    is_review_clean_verdict,
    is_review_complete_verdict,
)
from claude_auto_review.state.reviews.parsing import parse_review_findings
from claude_auto_review.state.reviews.review_text import extract_review_verdict_text


_CLEAN_VERDICT = "Clean - no issues found. Claude may stop."
_FINDINGS_VERDICT = "Findings present. Claude must address all findings before stopping."


def _replace_verdict_text(content: str, new_verdict: str) -> str:
    if "## Verdict" not in content:
        return content
    before, after = content.split("## Verdict", 1)
    lines = after.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip():
            lines[index] = new_verdict + ("\r\n" if line.endswith("\r\n") else "\n")
            break
    else:
        lines.append(new_verdict + "\n")
    return before + "## Verdict" + "".join(lines)


def _log_normalization(project_root, client_id, original_verdict, normalized_verdict):
    if project_root is None:
        project_root = Path.cwd()
    log_event(
        project_root,
        "review_verdict_normalized",
        client_id=client_id,
        original_verdict=original_verdict,
        normalized_verdict=normalized_verdict,
    )


def _rewrite_verdict(content: str, original_verdict: str, normalized_verdict: str, project_root, client_id) -> str:
    rewritten = _replace_verdict_text(content, normalized_verdict)
    if rewritten != content:
        _log_normalization(project_root, client_id, original_verdict, normalized_verdict)
    return rewritten


def _normalize_clean_verdict(content: str, verdict: str, client_id: str | None, minimum_blocking_severity: str, project_root: Path | None) -> str:
    parsed = parse_review_findings(content)
    if parsed and has_blocking_review_findings(content, minimum_blocking_severity):
        return _rewrite_verdict(content, verdict, _FINDINGS_VERDICT, project_root, client_id)
    return content


def _normalize_findings_verdict(content: str, verdict: str, client_id: str | None, minimum_blocking_severity: str, project_root: Path | None) -> str:
    if not has_blocking_review_findings(content, minimum_blocking_severity):
        return _rewrite_verdict(content, verdict, _CLEAN_VERDICT, project_root, client_id)
    return content


def normalize_review_verdict_content(
    content: str | None,
    client_id: str | None = None,
    minimum_blocking_severity: str = DEFAULT_MINIMUM_BLOCKING_SEVERITY,
    project_root: Path | None = None,
) -> str | None:
    if not content:
        return content
    if "## Verdict" not in content:
        return content

    verdict = extract_review_verdict_text(content)
    if not verdict or not is_review_complete_verdict(verdict):
        return content

    if is_review_clean_verdict(verdict):
        return _normalize_clean_verdict(content, verdict, client_id, minimum_blocking_severity, project_root)
    return _normalize_findings_verdict(content, verdict, client_id, minimum_blocking_severity, project_root)
