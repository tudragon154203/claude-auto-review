import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.support_paths import FAKE_ROOT
from claude_auto_review.config.settings.models import PluginSettings
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.snapshots.snapshot import StateSnapshot
from claude_auto_review.stop.classifier.enums import ClassifierStatus
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.orchestration.types.resolution import StopDecisionKind, TerminalResolution
from claude_auto_review.stop.orchestration.pipeline.stages import (
    _build_classifier_result_persistor,
    run_allow_no_unreviewed_stage,
    run_circuit_breaker_stage,
    run_classifier_stage,
    run_enabled_stage,
    run_pending_stage,
    run_state_stage,
)
from claude_auto_review.stop.reviews.types.enums import StopAllowReason


def _ctx(**kwargs):
    return RuntimeContext(
        project_root=kwargs.get("project_root", FAKE_ROOT),
        client_id=kwargs.get("client_id", "client-1"),
        settings=kwargs.get(
            "settings",
            PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=5),
        ),
    )


def _snapshot(events=None):
    events = events or [
        EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1", reviewed=False)
    ]
    return StateSnapshot.from_events(events)


class TestRunEnabledStage(unittest.TestCase):
    def test_enabled_returns_none(self):
        log_fn = MagicMock()
        result = run_enabled_stage(_ctx(), log_event_fn=log_fn)
        self.assertIsNone(result)
        log_fn.assert_not_called()

    def test_disabled_returns_allow_decision(self):
        log_fn = MagicMock()
        result = run_enabled_stage(_ctx(settings=PluginSettings(enabled=False)), log_event_fn=log_fn)
        self.assertEqual(result.kind, StopDecisionKind.ALLOW)
        self.assertEqual(result.reason, StopAllowReason.DISABLED)
        log_fn.assert_called_once()


class TestRunStateStage(unittest.TestCase):
    def test_returns_snapshot_state_and_unreviewed(self):
        snapshot = _snapshot()
        result = run_state_stage(
            _ctx(),
            load_state_snapshot_fn=MagicMock(return_value=snapshot),
            get_unreviewed_files_fn=MagicMock(return_value=["u1"]),
        )
        self.assertEqual(result, (snapshot, snapshot.events, ["u1"]))


class TestAllowNoUnreviewedStage(unittest.TestCase):
    def test_returns_none_when_unreviewed_exist(self):
        self.assertIsNone(run_allow_no_unreviewed_stage(["f1"]))

    def test_returns_allow_when_empty(self):
        result = run_allow_no_unreviewed_stage([])
        self.assertEqual(result.kind, StopDecisionKind.ALLOW)
        self.assertEqual(result.reason, StopAllowReason.NO_UNREVIEWED_FILES)


class TestCircuitBreakerStage(unittest.TestCase):
    def test_returns_none_below_limit(self):
        result = run_circuit_breaker_stage(
            _ctx(),
            _snapshot(),
            consecutive_stop_blocks_fn=MagicMock(return_value=2),
        )
        self.assertIsNone(result)

    def test_returns_allow_at_limit(self):
        result = run_circuit_breaker_stage(
            _ctx(settings=PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=2)),
            _snapshot(),
            consecutive_stop_blocks_fn=MagicMock(return_value=2),
        )
        self.assertEqual(result.kind, StopDecisionKind.ALLOW)
        self.assertEqual(result.reason, StopAllowReason.CIRCUIT_BREAKER)


class TestClassifierStage(unittest.TestCase):
    def test_returns_none_when_disabled(self):
        ctx = _ctx(
            settings=PluginSettings(enabled=True, last_assistant_message_classifier_enabled=False)
        )
        result = run_classifier_stage(ctx, classify_last_assistant_message_fn=MagicMock())
        self.assertIsNone(result)

    def test_returns_none_when_classifier_returns_none(self):
        result = run_classifier_stage(_ctx(), classify_last_assistant_message_fn=MagicMock(return_value=None))
        self.assertIsNone(result)

    def test_returns_none_when_classifier_not_incomplete(self):
        classifier_result = SimpleNamespace(status=ClassifierStatus.COMPLETE, reason="done")
        result = run_classifier_stage(
            _ctx(),
            classify_last_assistant_message_fn=MagicMock(return_value=classifier_result),
        )
        self.assertIsNone(result)

    def test_returns_allow_when_classifier_incomplete(self):
        classifier_result = SimpleNamespace(status=ClassifierStatus.INCOMPLETE, reason="missing")
        result = run_classifier_stage(
            _ctx(),
            classify_last_assistant_message_fn=MagicMock(return_value=classifier_result),
        )
        self.assertEqual(result.kind, StopDecisionKind.ALLOW)
        self.assertEqual(result.reason, StopAllowReason.CLASSIFIER_INCOMPLETE)

    def test_build_classifier_result_persistor_appends_state_entry(self):
        writer = MagicMock()
        writer_factory = MagicMock(return_value=writer)
        ctx = _ctx(settings=PluginSettings(enabled=True, debug=True))
        persistor = _build_classifier_result_persistor(ctx, writer_factory=writer_factory)
        result = MagicMock()
        result.as_state_entry.return_value = "entry-1"
        persistor(result)
        writer_factory.assert_called_once_with(FAKE_ROOT, "client-1")
        result.as_state_entry.assert_called_once_with(include_debug=True)
        writer.append.assert_called_once_with("entry-1")

    def test_uses_classifier_persist_factory_when_provided(self):
        persist = MagicMock()
        factory = MagicMock(return_value=persist)
        classify = MagicMock(return_value=SimpleNamespace(status=ClassifierStatus.COMPLETE, reason="ok"))
        ctx = _ctx()
        run_classifier_stage(
            ctx,
            classify_last_assistant_message_fn=classify,
            classifier_persist_factory=factory,
        )
        factory.assert_called_once_with(ctx)
        self.assertIs(classify.call_args.kwargs["persist"], persist)


class TestPendingStage(unittest.TestCase):
    def test_returns_terminal_decision(self):
        result = run_pending_stage(
            _ctx(),
            state=[],
            unreviewed=["u1"],
            resolve_pending_review_fn=MagicMock(return_value=TerminalResolution(exit_code=2)),
            get_reviewer_prompt_script_fn=MagicMock(return_value="reviewer.py"),
        )
        self.assertEqual(result.kind, StopDecisionKind.TERMINAL)
        self.assertEqual(result.details, {"exit_code": 2})


if __name__ == "__main__":
    unittest.main()
