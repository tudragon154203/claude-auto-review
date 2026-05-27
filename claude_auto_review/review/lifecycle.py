from __future__ import annotations

import os
import subprocess
from pathlib import Path

from claude_auto_review.config.constants import EXIT_REVIEW_FAILED
from claude_auto_review.review.completion import apply_completed_review, record_completed_review
from claude_auto_review.review.prompting.flow import create_review_prompt_files
from claude_auto_review.runtime.events import log_event
from claude_auto_review.stop.feedback import build_review_completion_prompt, build_unreviewed_files_string
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.resolution import StopFlowResolution
from claude_auto_review.stop.orchestration.review_artifact_evaluator import classify_review_artifact_state
from claude_auto_review.stop.reviews.prompt_runner import AutocompleteResult, attempt_stop_autocomplete
from claude_auto_review.stop.reviews.review_prompt_runner import (
    _block_review_prompt_failure,
    _reload_client_state,
    _review_prompt_path,
    run_review_prompt,
)
from claude_auto_review.stop.reviews.selection import find_pending_review_for_files


_AUTOCOMPLETE_RETRY_ATTEMPTS = 2


def build_review_prompt_env(payload):
    env = os.environ.copy()
    session_id = payload.get("session_id")
    if session_id:
        env["CLAUDE_SESSION_ID"] = session_id
    return env


class ReviewLifecycleService:
    def __init__(self, ctx: RuntimeContext):
        self.ctx = ctx

    def find_pending_review(self, state, unreviewed, timeout_hours):
        return find_pending_review_for_files(state, unreviewed, self.ctx.project_root, timeout_hours)

    def create_review_prompt(self, unreviewed, settings=None):
        return create_review_prompt_files(self.ctx, unreviewed, settings=settings)

    def execute_review_prompt(self, unreviewed, timeout_hours, review_prompt_script, files_str=None):
        files_str = files_str or build_unreviewed_files_string(unreviewed)
        env = build_review_prompt_env(self.ctx.payload)
        try:
            result = run_review_prompt(self.ctx, review_prompt_script, env)
        except subprocess.TimeoutExpired:
            return self.fail_review(files_str, EXIT_REVIEW_FAILED, "stop_hook_review_timeout", script=review_prompt_script)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            return self.fail_review(files_str, EXIT_REVIEW_FAILED, "stop_hook_review_error", error=error)
        return self.resolve_prompted_review(timeout_hours, files_str, result)

    def fail_review(self, files_str, exit_code, event_type, script=None, error=None):
        log_event(
            self.ctx.project_root,
            event_type,
            client_id=self.ctx.client_id,
            script=str(script) if script else None,
            error=str(error) if error else None,
        )
        return StopFlowResolution(state=[], unreviewed=[], exit_code=exit_code)

    def resolve_prompted_review(self, timeout_hours, files_str, result):
        state, unreviewed = _reload_client_state(self.ctx)
        if not unreviewed:
            log_event(
                self.ctx.project_root,
                "stop_approved",
                client_id=self.ctx.client_id,
                reason="no_unreviewed_files_after_review",
            )
            return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=0)

        review = self.find_pending_review(state, unreviewed, timeout_hours)
        if not review:
            _block_review_prompt_failure(files_str, result)
            return StopFlowResolution(state=state, unreviewed=unreviewed, exit_code=EXIT_REVIEW_FAILED)

        return StopFlowResolution(state=state, unreviewed=unreviewed, review=review)

    def classify_artifact_state(self, review_path: Path):
        return classify_review_artifact_state(
            review_path,
            minimum_blocking_severity=self.ctx.settings.minimum_blocking_severity,
            client_id=self.ctx.client_id,
        )

    def attempt_autocomplete(self, review_id, review_path, prompt_file, *, user_prompt=None):
        user_prompt = user_prompt or build_review_completion_prompt(review_path)
        reviewer_timeout_seconds = self.ctx.settings.reviewer_timeout_seconds
        reviewer_backend = self.ctx.settings.resolved_reviewer_backend()
        reviewer_model = self.ctx.settings.resolved_reviewer_model(backend=reviewer_backend)

        result: AutocompleteResult | None = None
        for attempt in range(_AUTOCOMPLETE_RETRY_ATTEMPTS):
            result = attempt_stop_autocomplete(
                self.ctx,
                review_id,
                review_path,
                prompt_file,
                user_prompt,
                reviewer_timeout_seconds=reviewer_timeout_seconds,
                model=reviewer_model,
                backend=reviewer_backend,
            )
            if result.status != "empty_stdout":
                break
            if attempt == 0:
                log_event(self.ctx.project_root, "stop_hook_reviewer_retry", client_id=self.ctx.client_id, reviewId=review_id)
        return result

    def review_prompt_path(self, review_id):
        return _review_prompt_path(self.ctx, review_id)

    def apply_completed_review(self, review_id, covered_entries):
        return apply_completed_review(self.ctx.project_root, self.ctx.client_id, review_id, covered_entries)

    def record_completed_review(self, review_id, covered_entries):
        return record_completed_review(self.ctx.project_root, self.ctx.client_id, review_id, covered_entries)
