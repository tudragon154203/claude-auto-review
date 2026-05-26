import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.state.models import EditRecord, StopBlockedRecord
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.orchestration.flow import run_stop_flow

_STATE = [EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1", reviewed=False)]


def _snapshot(*, events=_STATE):
    return StateSnapshot.from_events(events)


class TestFlowFinalize(unittest.TestCase):

    @patch("claude_auto_review.stop.orchestration.decision_engine.log_event")
    @patch("claude_auto_review.stop.orchestration.decision_engine.load_state_snapshot", return_value=_snapshot())
    @patch("claude_auto_review.stop.orchestration.decision_engine.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.decision_engine.load_settings")
    def test_disabled_setting_returns_0_and_logs_stop_disabled(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_log,
    ):
        mock_settings.return_value = PluginSettings(
            enabled=False,
            pending_review_timeout_hours=1,
            max_stop_passes=5,
        )

        result = run_stop_flow(Path("/fake"), {"session_id": "sid"})

        self.assertEqual(result, 0)
        mock_log.assert_called_once_with(Path("/fake"), "stop_disabled", client_id="sid")

    @patch("claude_auto_review.stop.orchestration.decision_engine.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.decision_engine.finalize_review_stop", return_value=2)
    @patch("claude_auto_review.stop.orchestration.decision_engine.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.decision_engine.load_state_snapshot", return_value=_snapshot())
    @patch("claude_auto_review.stop.orchestration.decision_engine.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.decision_engine.load_settings")
    def test_non_terminal_resolution_is_forwarded_to_finalize(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_resolve,
        mock_finalize,
        mock_classify,
    ):
        mock_settings.return_value = PluginSettings(
            enabled=True,
            pending_review_timeout_hours=1,
            max_stop_passes=5,
            last_assistant_message_classifier_enabled=True,
        )
        mock_classify.return_value = SimpleNamespace(status="complete", reason="parsed_label")
        mock_resolve.return_value.is_terminal = False
        mock_resolve.return_value.exit_code = None

        result = run_stop_flow(Path("/fake"), {"session_id": "sid", "last_assistant_message": "done"})

        self.assertEqual(result, 2)
        mock_finalize.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.decision_engine.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.decision_engine.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.decision_engine.load_state_snapshot", return_value=_snapshot())
    @patch("claude_auto_review.stop.orchestration.decision_engine.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.decision_engine.load_settings")
    def test_invalid_numeric_settings_fall_back_to_defaults(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_resolve,
        mock_classify,
    ):
        mock_settings.return_value = PluginSettings.from_mapping(
            {
                "enabled": True,
                "pendingReviewTimeoutHours": "not-a-number",
                "maxStopPasses": "also-bad",
            }
        )
        mock_classify.return_value = None
        mock_resolve.return_value.is_terminal = True
        mock_resolve.return_value.exit_code = 2

        result = run_stop_flow(Path("/fake"), {"session_id": "sid"})

        self.assertEqual(result, 2)
        self.assertEqual(mock_resolve.call_args.args[3], 1.0)


if __name__ == "__main__":
    unittest.main()

