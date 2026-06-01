import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.finalize_outcomes import FinalizeEffect
from claude_auto_review.stop.orchestration.finalize_plan_executor import (
    _apply_completed_clean_review_result,
    _apply_finalize_plan_result,
)
from claude_auto_review.stop.orchestration.resolution import FinalizeAction, FinalizeResult
from tests.support_paths import FAKE_ROOT


def _ctx(**kwargs):
    return RuntimeContext(
        project_root=kwargs.get("project_root", FAKE_ROOT),
        client_id=kwargs.get("client_id", "sid"),
        settings=kwargs.get(
            "settings", PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=5)
        ),
        payload=kwargs.get("payload", {}),
    )


class TestApplyCompletedCleanReviewResult(unittest.TestCase):
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.log_event")
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.apply_completed_review")
    def test_no_remaining_returns_approved(self, mock_apply, mock_log):
        mock_apply.return_value = []
        ctx = _ctx()
        result, payload = _apply_completed_clean_review_result(ctx, "r1", [])
        self.assertEqual(result.action, FinalizeAction.APPROVED)
        self.assertEqual(result.exit_code, 0)
        self.assertIsNotNone(payload)
        mock_log.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.apply_completed_review")
    def test_remaining_returns_partial_review(self, mock_apply):
        mock_apply.return_value = ["file1.ts"]
        ctx = _ctx()
        result, payload = _apply_completed_clean_review_result(ctx, "r1", [])
        self.assertEqual(result.action, FinalizeAction.BLOCKED_PARTIAL_REVIEW)
        self.assertEqual(result.exit_code, 2)


class TestApplyFinalizePlanResult(unittest.TestCase):
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor._apply_completed_clean_review_result")
    def test_apply_completed_clean_review_effect(self, mock_apply_clean):
        expected = (FinalizeResult(action=FinalizeAction.APPROVED, exit_code=0), MagicMock())
        mock_apply_clean.return_value = expected
        plan = MagicMock(effect=FinalizeEffect.APPLY_COMPLETED_CLEAN_REVIEW)
        ctx = _ctx()
        writer = MagicMock()
        result = _apply_finalize_plan_result(ctx, plan, "r1", Path("/review.md"), [], [], state_event_writer=writer)
        self.assertEqual(result, expected)

    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.finalize_plan_executor.record_completed_review")
    def test_record_findings_block_effect(self, mock_record, mock_block):
        block_result = MagicMock()
        block_result.state_record = MagicMock()
        mock_block.return_value = block_result
        plan = MagicMock(
            effect=FinalizeEffect.RECORD_FINDINGS_BLOCK,
            result=FinalizeResult(action=FinalizeAction.BLOCKED_FINDINGS, exit_code=2),
        )
        ctx = _ctx()
        writer = MagicMock()
        emitter = MagicMock()
        result, payload = _apply_finalize_plan_result(ctx, plan, "r1", Path("/review.md"), [], [], state_event_writer=writer, emitter=emitter)
        self.assertEqual(result.action, FinalizeAction.BLOCKED_FINDINGS)
        self.assertIsNone(payload)
        mock_record.assert_called_once()
        mock_block.assert_called_once()
        writer.append.assert_called_once_with(block_result.state_record)

    def test_unsupported_effect_raises_value_error(self):
        plan = MagicMock(effect="unsupported_effect")
        ctx = _ctx()
        writer = MagicMock()
        with self.assertRaises(ValueError):
            _apply_finalize_plan_result(ctx, plan, "r1", Path("/review.md"), [], [], state_event_writer=writer)


if __name__ == "__main__":
    unittest.main()
