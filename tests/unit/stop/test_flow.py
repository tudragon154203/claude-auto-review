import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.stop.flow import run_stop_flow


class TestRunStopFlow(unittest.TestCase):
    @patch("claude_auto_review.stop.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.flow.get_unreviewed_files", return_value=[])
    @patch("claude_auto_review.stop.flow.load_state", return_value=[])
    @patch("claude_auto_review.stop.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.flow.load_settings")
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

    @patch("claude_auto_review.stop.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.flow.consecutive_stop_blocks", return_value=3)
    @patch("claude_auto_review.stop.flow.get_unreviewed_files", return_value=[{"file": "a.ts", "hash": "1"}])
    @patch("claude_auto_review.stop.flow.load_state", return_value=[{"type": "edit", "file": "a.ts", "hash": "1", "reviewed": False}])
    @patch("claude_auto_review.stop.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.flow.load_settings")
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

    @patch("claude_auto_review.stop.flow.resolve_pending_review")
    @patch("claude_auto_review.stop.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.flow.consecutive_stop_blocks", return_value=0)
    @patch("claude_auto_review.stop.flow.get_unreviewed_files", return_value=[{"file": "a.ts", "hash": "1"}])
    @patch("claude_auto_review.stop.flow.load_state", return_value=[{"type": "edit", "file": "a.ts", "hash": "1", "reviewed": False}])
    @patch("claude_auto_review.stop.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.flow.load_settings")
    def test_classifier_invoked_when_enabled(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_unreviewed,
        mock_blocks,
        mock_classify,
        mock_resolve,
    ):
        mock_settings.return_value = {
            "enabled": True,
            "pendingReviewTimeoutHours": 1,
            "maxStopPasses": 3,
            "lastAssistantMessageClassifierEnabled": True,
        }
        mock_resolve.return_value.is_terminal = True
        mock_resolve.return_value.exit_code = 0

        result = run_stop_flow(Path("/fake"), {"session_id": "sid", "last_assistant_message": "done"})

        self.assertEqual(result, 0)
        mock_classify.assert_called_once_with(
            Path("/fake"),
            "sid",
            {"session_id": "sid", "last_assistant_message": "done"},
            mock_settings.return_value,
        )

    @patch("claude_auto_review.stop.flow.resolve_pending_review")
    @patch("claude_auto_review.stop.flow.classify_last_assistant_message")
    @patch("claude_auto_review.stop.flow.consecutive_stop_blocks", return_value=0)
    @patch("claude_auto_review.stop.flow.get_unreviewed_files", return_value=[{"file": "a.ts", "hash": "1"}])
    @patch("claude_auto_review.stop.flow.load_state", return_value=[{"type": "edit", "file": "a.ts", "hash": "1", "reviewed": False}])
    @patch("claude_auto_review.stop.flow.ensure_client_runtime")
    @patch("claude_auto_review.stop.flow.load_settings")
    def test_disabled_setting_bypasses_classifier_without_changing_result(
        self,
        mock_settings,
        mock_runtime,
        mock_state,
        mock_unreviewed,
        mock_blocks,
        mock_classify,
        mock_resolve,
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
