import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from claude_auto_review.state.models import EditRecord
from claude_auto_review.stop.orchestration.flow import run_stop_flow

_UNREVIEWED = [EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1")]
_STATE = [EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1", reviewed=False)]


class TestRunStopFlow(unittest.TestCase):
    @patch("claude_auto_review.stop.orchestration.flow.log_event")
    @patch("claude_auto_review.stop.orchestration.flow.get_unreviewed_files", return_value=_UNREVIEWED)
    @patch("claude_auto_review.stop.orchestration.flow.load_state", return_value=_STATE)
    @patch("claude_auto_review.stop.orchestration.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.flow.load_settings")
    def test_disabled_setting_returns_0_and_logs_stop_disabled(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_unreviewed,
        mock_log,
    ):
        mock_settings.return_value = {
            "enabled": False,
            "pendingReviewTimeoutHours": 1,
            "maxStopPasses": 3,
        }

        result = run_stop_flow(Path("/fake"), {"session_id": "sid"})

        self.assertEqual(result, 0)
        mock_log.assert_called_once_with(Path("/fake"), "stop_disabled")

    @patch("claude_auto_review.stop.orchestration.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.flow.get_unreviewed_files", return_value=[])
    @patch("claude_auto_review.stop.orchestration.flow.load_state", return_value=[])
    @patch("claude_auto_review.stop.orchestration.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.flow.load_settings")
    def test_classifier_skipped_when_no_unreviewed_files(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_unreviewed,
        mock_classify,
    ):
        mock_settings.return_value = {
            "enabled": True,
            "pendingReviewTimeoutHours": 1,
            "maxStopPasses": 3,
            "lastAssistantMessageClassifierEnabled": True,
        }

        result = run_stop_flow(Path("/fake"), {"session_id": "sid", "last_assistant_message": "done"})

        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.flow.consecutive_stop_blocks", return_value=3)
    @patch("claude_auto_review.stop.orchestration.flow.get_unreviewed_files", return_value=_UNREVIEWED)
    @patch("claude_auto_review.stop.orchestration.flow.load_state", return_value=_STATE)
    @patch("claude_auto_review.stop.orchestration.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.flow.load_settings")
    def test_classifier_skipped_when_circuit_breaker_allows_stop(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_unreviewed,
        mock_blocks,
        mock_classify,
    ):
        mock_settings.return_value = {
            "enabled": True,
            "pendingReviewTimeoutHours": 1,
            "maxStopPasses": 3,
            "lastAssistantMessageClassifierEnabled": True,
        }

        result = run_stop_flow(Path("/fake"), {"session_id": "sid", "last_assistant_message": "done"})

        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.flow.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.flow.consecutive_stop_blocks", return_value=0)
    @patch("claude_auto_review.stop.orchestration.flow.get_unreviewed_files", return_value=_UNREVIEWED)
    @patch("claude_auto_review.stop.orchestration.flow.load_state", return_value=_STATE)
    @patch("claude_auto_review.stop.orchestration.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.flow.load_settings")
    def test_classifier_invoked_when_enabled(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_unreviewed,
        mock_blocks,
        mock_resolve,
        mock_classify,
    ):
        mock_settings.return_value = {
            "enabled": True,
            "pendingReviewTimeoutHours": 1,
            "maxStopPasses": 3,
            "lastAssistantMessageClassifierEnabled": True,
        }
        mock_classify.return_value = SimpleNamespace(status="complete", reason="parsed_label")
        mock_resolve.return_value.is_terminal = True
        mock_resolve.return_value.exit_code = 0

        result = run_stop_flow(Path("/fake"), {"session_id": "sid", "last_assistant_message": "done"})

        self.assertEqual(result, 0)
        mock_classify.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.flow.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.flow.consecutive_stop_blocks", return_value=0)
    @patch("claude_auto_review.stop.orchestration.flow.get_unreviewed_files", return_value=_UNREVIEWED)
    @patch("claude_auto_review.stop.orchestration.flow.load_state", return_value=_STATE)
    @patch("claude_auto_review.stop.orchestration.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.flow.load_settings")
    def test_classifier_incomplete_allows_stop_before_review_resolution(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_unreviewed,
        mock_blocks,
        mock_resolve,
        mock_classify,
    ):
        mock_settings.return_value = {
            "enabled": True,
            "pendingReviewTimeoutHours": 1,
            "maxStopPasses": 3,
            "lastAssistantMessageClassifierEnabled": True,
        }
        mock_classify.return_value = SimpleNamespace(status="incomplete", reason="parsed_label")

        result = run_stop_flow(Path("/fake"), {"session_id": "sid", "last_assistant_message": "done"})

        self.assertEqual(result, 0)
        mock_resolve.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.flow.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.flow.consecutive_stop_blocks", return_value=0)
    @patch("claude_auto_review.stop.orchestration.flow.get_unreviewed_files", return_value=_UNREVIEWED)
    @patch("claude_auto_review.stop.orchestration.flow.load_state", return_value=_STATE)
    @patch("claude_auto_review.stop.orchestration.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.flow.load_settings")
    def test_disabled_setting_bypasses_classifier_without_changing_result(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_unreviewed,
        mock_blocks,
        mock_resolve,
        mock_classify,
    ):
        mock_settings.return_value = {
            "enabled": True,
            "pendingReviewTimeoutHours": 1,
            "maxStopPasses": 3,
            "lastAssistantMessageClassifierEnabled": False,
        }
        mock_resolve.return_value.is_terminal = True
        mock_resolve.return_value.exit_code = 2

        result = run_stop_flow(Path("/fake"), {"session_id": "sid", "last_assistant_message": "done"})

        self.assertEqual(result, 2)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.flow.finalize_review_stop", return_value=2)
    @patch("claude_auto_review.stop.orchestration.flow.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.flow.consecutive_stop_blocks", return_value=0)
    @patch("claude_auto_review.stop.orchestration.flow.get_unreviewed_files", return_value=_UNREVIEWED)
    @patch("claude_auto_review.stop.orchestration.flow.load_state", return_value=_STATE)
    @patch("claude_auto_review.stop.orchestration.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.flow.load_settings")
    def test_non_terminal_resolution_is_forwarded_to_finalize(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_unreviewed,
        mock_blocks,
        mock_resolve,
        mock_finalize,
        mock_classify,
    ):
        mock_settings.return_value = {
            "enabled": True,
            "pendingReviewTimeoutHours": 1,
            "maxStopPasses": 3,
            "lastAssistantMessageClassifierEnabled": True,
        }
        mock_classify.return_value = SimpleNamespace(status="complete", reason="parsed_label")
        mock_resolve.return_value.is_terminal = False
        mock_resolve.return_value.exit_code = None

        result = run_stop_flow(Path("/fake"), {"session_id": "sid", "last_assistant_message": "done"})

        self.assertEqual(result, 2)
        mock_finalize.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.flow.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.flow.consecutive_stop_blocks", return_value=0)
    @patch("claude_auto_review.stop.orchestration.flow.get_unreviewed_files", return_value=_UNREVIEWED)
    @patch("claude_auto_review.stop.orchestration.flow.load_state", return_value=_STATE)
    @patch("claude_auto_review.stop.orchestration.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.orchestration.flow.load_settings")
    def test_invalid_numeric_settings_fall_back_to_defaults(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_unreviewed,
        mock_blocks,
        mock_resolve,
        mock_classify,
    ):
        mock_settings.return_value = {
            "enabled": True,
            "pendingReviewTimeoutHours": "not-a-number",
            "maxStopPasses": "also-bad",
        }
        mock_classify.return_value = None
        mock_resolve.return_value.is_terminal = True
        mock_resolve.return_value.exit_code = 2

        result = run_stop_flow(Path("/fake"), {"session_id": "sid"})

        self.assertEqual(result, 2)
        self.assertEqual(mock_resolve.call_args.args[3], 1.0)
