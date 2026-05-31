import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.state.models import EditRecord
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.classifier.enums import ClassifierStatus
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.resolution import (
    StopDecisionKind,
    TerminalResolution,
    ReviewResolution,
)
from claude_auto_review.stop.orchestration.stages import (
    run_allow_no_unreviewed_stage,
    run_circuit_breaker_stage,
    run_classifier_stage,
    run_enabled_stage,
    run_pending_stage,
    run_state_stage,
)
from claude_auto_review.stop.reviews.enums import StopAllowReason


def _ctx(**kwargs):
    return RuntimeContext(
        project_root=kwargs.get("project_root", Path("/fake")),
        client_id=kwargs.get("client_id", "sid"),
        settings=kwargs.get(
            "settings", PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=5)
        ),
        payload=kwargs.get("payload", {}),
    )


def _snapshot(events=None):
    events = events or [EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1", reviewed=False)]
    return StateSnapshot.from_events(events)


class TestRunEnabledStage(unittest.TestCase):
    def test_enabled_returns_none(self):
        log_fn = MagicMock()
        result = run_enabled_stage(_ctx(), log_event_fn=log_fn)
        self.assertIsNone(result)
        log_fn.assert_not_called()

    def test_disabled_returns_allow(self):
        log_fn = MagicMock()
        ctx = _ctx(settings=PluginSettings(enabled=False))
        result = run_enabled_stage(ctx, log_event_fn=log_fn)
        self.assertEqual(result.kind, StopDecisionKind.ALLOW)
        self.assertEqual(result.reason, StopAllowReason.DISABLED)
        log_fn.assert_called_once()


class TestRunStateStage(unittest.TestCase):
    def test_returns_snapshot_state_unreviewed(self):
        snapshot = _snapshot()
        load_fn = MagicMock(return_value=snapshot)
        unreviewed_fn = MagicMock(return_value=snapshot.unreviewed_files)
        state_snapshot, state, unreviewed = run_state_stage(_ctx(), load_state_snapshot_fn=load_fn, get_unreviewed_files_fn=unreviewed_fn)
        self.assertIs(state_snapshot, snapshot)
        self.assertEqual(state, snapshot.events)
        self.assertEqual(unreviewed, snapshot.unreviewed_files)


class TestRunAllowNoUnreviewedStage(unittest.TestCase):
    def test_empty_returns_allow(self):
        result = run_allow_no_unreviewed_stage([])
        self.assertEqual(result.kind, StopDecisionKind.ALLOW)
        self.assertEqual(result.reason, StopAllowReason.NO_UNREVIEWED_FILES)

    def test_non_empty_returns_none(self):
        result = run_allow_no_unreviewed_stage([EditRecord(timestamp="t", file="a.ts", hash="1", reviewed=False)])
        self.assertIsNone(result)


class TestRunCircuitBreakerStage(unittest.TestCase):
    def test_under_limit_returns_none(self):
        counter_fn = MagicMock(return_value=3)
        ctx = _ctx(settings=PluginSettings(enabled=True, max_stop_passes=5))
        result = run_circuit_breaker_stage(ctx, _snapshot(), consecutive_stop_blocks_fn=counter_fn)
        self.assertIsNone(result)

    def test_at_limit_returns_allow(self):
        counter_fn = MagicMock(return_value=5)
        ctx = _ctx(settings=PluginSettings(enabled=True, max_stop_passes=5))
        result = run_circuit_breaker_stage(ctx, _snapshot(), consecutive_stop_blocks_fn=counter_fn)
        self.assertEqual(result.kind, StopDecisionKind.ALLOW)
        self.assertEqual(result.reason, StopAllowReason.CIRCUIT_BREAKER)
        self.assertEqual(result.details["block_count"], 5)

    def test_over_limit_returns_allow(self):
        counter_fn = MagicMock(return_value=10)
        ctx = _ctx(settings=PluginSettings(enabled=True, max_stop_passes=5))
        result = run_circuit_breaker_stage(ctx, _snapshot(), consecutive_stop_blocks_fn=counter_fn)
        self.assertEqual(result.kind, StopDecisionKind.ALLOW)


class TestRunClassifierStage(unittest.TestCase):
    def test_classifier_disabled_returns_none(self):
        ctx = _ctx(settings=PluginSettings(enabled=True, last_assistant_message_classifier_enabled=False))
        result = run_classifier_stage(ctx, classify_last_assistant_message_fn=MagicMock())
        self.assertIsNone(result)

    def test_classifier_returns_none(self):
        ctx = _ctx(settings=PluginSettings(enabled=True, last_assistant_message_classifier_enabled=True))
        result = run_classifier_stage(ctx, classify_last_assistant_message_fn=MagicMock(return_value=None))
        self.assertIsNone(result)

    def test_classifier_incomplete_returns_allow(self):
        ctx = _ctx(settings=PluginSettings(enabled=True, last_assistant_message_classifier_enabled=True))
        classifier_result = SimpleNamespace(status=ClassifierStatus.INCOMPLETE, reason="test")
        result = run_classifier_stage(ctx, classify_last_assistant_message_fn=MagicMock(return_value=classifier_result))
        self.assertEqual(result.kind, StopDecisionKind.ALLOW)
        self.assertEqual(result.reason, StopAllowReason.CLASSIFIER_INCOMPLETE)

    def test_classifier_complete_returns_none(self):
        ctx = _ctx(settings=PluginSettings(enabled=True, last_assistant_message_classifier_enabled=True))
        classifier_result = SimpleNamespace(status=ClassifierStatus.COMPLETE, reason=None)
        result = run_classifier_stage(ctx, classify_last_assistant_message_fn=MagicMock(return_value=classifier_result))
        self.assertIsNone(result)


class TestRunPendingStage(unittest.TestCase):
    def test_terminal_resolution_returns_terminal(self):
        resolve_fn = MagicMock(return_value=TerminalResolution(exit_code=2))
        script_fn = MagicMock(return_value="reviewer.py")
        result = run_pending_stage(_ctx(), [], [], resolve_pending_review_fn=resolve_fn, get_reviewer_prompt_script_fn=script_fn)
        self.assertEqual(result.kind, StopDecisionKind.TERMINAL)
        self.assertEqual(result.details["exit_code"], 2)

    def test_review_resolution_returns_finalize(self):
        review_meta = MagicMock()
        resolve_fn = MagicMock(return_value=ReviewResolution(review=review_meta, state=[], unreviewed=[]))
        script_fn = MagicMock(return_value="reviewer.py")
        result = run_pending_stage(_ctx(), [], [], resolve_pending_review_fn=resolve_fn, get_reviewer_prompt_script_fn=script_fn)
        self.assertEqual(result.kind, StopDecisionKind.FINALIZE)
        self.assertIn("resolution", result.details)

    def test_emitter_forwarded_to_resolve(self):
        emitter = MagicMock()
        resolve_fn = MagicMock(return_value=TerminalResolution(exit_code=2))
        script_fn = MagicMock(return_value="reviewer.py")
        run_pending_stage(_ctx(), [], [], resolve_pending_review_fn=resolve_fn, get_reviewer_prompt_script_fn=script_fn, emitter=emitter)
        _, kwargs = resolve_fn.call_args
        self.assertIs(kwargs["emitter"], emitter)


if __name__ == "__main__":
    unittest.main()
