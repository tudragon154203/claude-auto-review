from dataclasses import dataclass

from claude_auto_review.runtime.events import log_event
from claude_auto_review.state.reviews.verdicts import normalize_review_verdict_content
from claude_auto_review.stop.orchestration.core.context import RuntimeContext


@dataclass(frozen=True)
class AutocompleteResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None

    @property
    def output_written(self):
        return self.status == "output_written"

    def __bool__(self):
        return self.output_written


def _process_review_result(ctx: RuntimeContext, result, review_path, review_id, backend):
    stdout_len = len(result.stdout) if result.stdout else 0
    log_event(
        ctx.project_root,
        "stop_hook_reviewer_done",
        client_id=ctx.client_id,
        backend=backend,
        returncode=result.returncode,
        stdout_len=stdout_len,
        stdout=result.stdout[:500] if result.stdout else "",
        stderr=result.stderr[:500] if result.stderr else "",
    )

    if result.returncode != 0:
        log_event(
            ctx.project_root,
            "stop_hook_reviewer_nonzero",
            client_id=ctx.client_id,
            backend=backend,
            returncode=result.returncode,
            reviewId=review_id,
            stderr=result.stderr[:500] if result.stderr else "",
        )
        return AutocompleteResult(
            status="nonzero",
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            returncode=result.returncode,
        )

    if not result.stdout.strip():
        log_event(
            ctx.project_root,
            "stop_hook_reviewer_empty",
            client_id=ctx.client_id,
            backend=backend,
            reviewId=review_id,
            stdout_len=stdout_len,
            stderr=result.stderr[:500] if result.stderr else "",
        )
        return AutocompleteResult(
            status="empty_stdout",
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            returncode=result.returncode,
        )

    normalized_output = normalize_review_verdict_content(result.stdout)
    review_path.write_text(normalized_output, encoding="utf-8", newline="\n")
    log_event(
        ctx.project_root,
        "stop_hook_reviewer_output_written",
        client_id=ctx.client_id,
        backend=backend,
        reviewId=review_id,
        stdout_len=stdout_len,
    )
    return AutocompleteResult(
        status="output_written",
        stdout=normalized_output,
        stderr=result.stderr or "",
        returncode=result.returncode,
    )
