from dataclasses import dataclass

from claude_auto_review.config.io import load_settings
from claude_auto_review.paths.path_utils import get_reviewer_prompt_script
from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.state.store.read import consecutive_stop_blocks, get_unreviewed_files, load_state_snapshot
from claude_auto_review.stop.classifier.last_assistant_message import classify_last_assistant_message
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.finalize import finalize_review_stop
from claude_auto_review.stop.orchestration.pending import resolve_pending_review


@dataclass(frozen=True)
class StopDecision:
    kind: str
    reason: str | None = None
    details: dict | None = None


class StopDecisionEngine:
    def __init__(
        self,
        project_root,
        payload,
        *,
        client_id=None,
        settings=None,
        load_settings_fn=None,
        get_client_id_fn=None,
        ensure_client_runtime_fn=None,
        load_state_snapshot_fn=None,
        get_unreviewed_files_fn=None,
        consecutive_stop_blocks_fn=None,
        classify_last_assistant_message_fn=None,
        resolve_pending_review_fn=None,
        finalize_review_stop_fn=None,
        get_reviewer_prompt_script_fn=None,
        log_event_fn=None,
    ):
        load_settings_fn = load_settings if load_settings_fn is None else load_settings_fn
        get_client_id_fn = get_client_id if get_client_id_fn is None else get_client_id_fn
        ensure_client_runtime_fn = ensure_client_runtime if ensure_client_runtime_fn is None else ensure_client_runtime_fn
        load_state_snapshot_fn = load_state_snapshot if load_state_snapshot_fn is None else load_state_snapshot_fn
        get_unreviewed_files_fn = get_unreviewed_files if get_unreviewed_files_fn is None else get_unreviewed_files_fn
        consecutive_stop_blocks_fn = consecutive_stop_blocks if consecutive_stop_blocks_fn is None else consecutive_stop_blocks_fn
        classify_last_assistant_message_fn = (
            classify_last_assistant_message if classify_last_assistant_message_fn is None else classify_last_assistant_message_fn
        )
        resolve_pending_review_fn = resolve_pending_review if resolve_pending_review_fn is None else resolve_pending_review_fn
        finalize_review_stop_fn = finalize_review_stop if finalize_review_stop_fn is None else finalize_review_stop_fn
        get_reviewer_prompt_script_fn = get_reviewer_prompt_script if get_reviewer_prompt_script_fn is None else get_reviewer_prompt_script_fn
        log_event_fn = log_event if log_event_fn is None else log_event_fn

        self._load_state_snapshot = load_state_snapshot_fn
        self._get_unreviewed_files = get_unreviewed_files_fn
        self._consecutive_stop_blocks = consecutive_stop_blocks_fn
        self._classify_last_assistant_message = classify_last_assistant_message_fn
        self._resolve_pending_review = resolve_pending_review_fn
        self._finalize_review_stop = finalize_review_stop_fn
        self._get_reviewer_prompt_script = get_reviewer_prompt_script_fn
        self._log_event = log_event_fn
        resolved_client_id = client_id or get_client_id_fn(payload.get("session_id"))
        ensure_client_runtime_fn(project_root, resolved_client_id)
        resolved_settings = settings or load_settings_fn(project_root)
        self.ctx = RuntimeContext(
            project_root=project_root,
            client_id=resolved_client_id,
            settings=resolved_settings,
            payload=payload,
        )

    def evaluate(self):
        settings = self.ctx.settings
        if not settings.enabled:
            self._log_event(self.ctx.project_root, "stop_disabled", client_id=self.ctx.client_id)
            return StopDecision(kind="allow", reason="disabled")

        timeout_hours = settings.pending_review_timeout_hours
        state_snapshot = self._load_state_snapshot(self.ctx.project_root, self.ctx.client_id)
        state = state_snapshot.events
        unreviewed = self._get_unreviewed_files(state_snapshot)

        if not unreviewed:
            return StopDecision(kind="allow", reason="no_unreviewed_files")

        block_count = self._consecutive_stop_blocks(state_snapshot)
        if block_count >= settings.max_stop_passes:
            return StopDecision(
                kind="allow",
                reason="circuit_breaker",
                details={"block_count": block_count, "max_passes": settings.max_stop_passes},
            )

        classifier_result = self._check_classifier_incomplete()
        if classifier_result is not None:
            return StopDecision(
                kind="allow",
                reason="classifier_incomplete",
                details={"classifier_status": classifier_result.status, "classifier_reason": classifier_result.reason},
            )

        resolution = self._resolve_pending_review(
            self.ctx,
            state,
            unreviewed,
            timeout_hours,
            self._get_reviewer_prompt_script(),
        )
        if resolution.is_terminal:
            return StopDecision(kind="terminal", details={"exit_code": resolution.exit_code})

        return StopDecision(kind="finalize", details={"resolution": resolution})

    def _check_classifier_incomplete(self):
        if not self.ctx.settings.last_assistant_message_classifier_enabled:
            return None
        result = self._classify_last_assistant_message(self.ctx)
        if result is not None and result.status == "incomplete":
            return result
        return None

    def finalize(self, resolution):
        return self._finalize_review_stop(self.ctx, resolution)
