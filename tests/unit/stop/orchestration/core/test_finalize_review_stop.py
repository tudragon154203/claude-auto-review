import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.state.models import EditRecord, ReviewMetadata
from claude_auto_review.stop.orchestration.core.context import RuntimeContext
from claude_auto_review.stop.orchestration.core.finalize import _review_artifact_state, finalize_review_stop
from claude_auto_review.stop.orchestration.core.resolution import StopFlowResolution


def _mk_review(reviewId: str = "r1", reviewPath: str = "/fake/r.md") -> ReviewMetadata:
    return ReviewMetadata(
        timestamp="2026-05-11T10:00:00+07:00",
        reviewId=reviewId,
        reviewPath=reviewPath,
        files=[],
        clientId="c",
        status="pending",
    )


def _ctx(project_root=Path("/fake"), client_id="c", settings=None, payload=None):
    return RuntimeContext(
        project_root=project_root,
        client_id=client_id,
        settings=settings if settings is not None else {},
        payload=payload if payload is not None else {},
    )


class TestFinalizeReviewStop(unittest.TestCase):
    resolution = StopFlowResolution(
        state=[],
        unreviewed=[],
        review=_mk_review("r1"),
    )

    def test_review_artifact_state_detects_clean_complete_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "review.md"
            review_path.write_text("## Verdict\nClean\n", encoding="utf-8")

            artifact_state = _review_artifact_state(review_path)

        self.assertEqual(artifact_state.status, "complete_clean")
        self.assertEqual(artifact_state.verdict, "Clean")

    def test_review_artifact_state_normalizes_contradictory_clean_review(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "review.md"
            review_path.write_text(
                "## Findings\n"
                "### [Low] Unused import\n"
                "**Verdict:** Confirmed\n\n"
                "## Verdict\n"
                "Clean - no issues found. Claude may stop.\n",
                encoding="utf-8",
            )

            artifact_state = _review_artifact_state(review_path)

            self.assertEqual(artifact_state.status, "complete_findings")
            self.assertIn(
                "Findings present. Claude must address all findings before stopping.",
                review_path.read_text(encoding="utf-8"),
            )

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.is_review_clean", return_value=True)
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", return_value="Clean")
    def test_completed_no_remaining_returns_0(self, mock_verdict, mock_clean, mock_apply, mock_covered):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 0)

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.record_completed_review")
    @patch("claude_auto_review.stop.orchestration.core.finalize.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", return_value="Has findings")
    def test_completed_with_findings_returns_2(self, mock_verdict, mock_block, mock_record, mock_covered):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)
        mock_block.assert_called_once()
        mock_record.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.record_completed_review")
    @patch("claude_auto_review.stop.orchestration.core.finalize.block_completed_review_findings")
    def test_completed_clean_verdict_with_findings_blocks(self, mock_block, mock_record, mock_covered):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            review_dir = project_root / "fake"
            review_dir.mkdir(parents=True, exist_ok=True)
            review_path = review_dir / "r.md"
            review_path.write_text(
                "## Findings\n"
                "### [Low] Unused import\n"
                "**Verdict:** Confirmed\n\n"
                "## Verdict\n"
                "Clean - no issues found. Claude may stop.\n",
                encoding="utf-8",
            )
            resolution = StopFlowResolution(state=[], unreviewed=[], review=_mk_review("r1", "fake/r.md"))
            result = finalize_review_stop(_ctx(project_root=project_root), resolution)
            self.assertEqual(result, 2)
            mock_record.assert_called_once()
            mock_block.assert_called_once()
            self.assertIn(
                "Findings present. Claude must address all findings before stopping.",
                review_path.read_text(encoding="utf-8"),
            )

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.is_review_clean", return_value=True)
    @patch("claude_auto_review.stop.orchestration.core.finalize.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.core.finalize.attempt_stop_autocomplete", return_value=MagicMock(status="output_written"))
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", side_effect=["Pending.", "Clean"])
    def test_pending_review_autocomplete_clean_returns_0(
        self, mock_verdict, mock_auto, mock_prompt, mock_clean, mock_apply, mock_covered
    ):
        mock_prompt.return_value = "Complete the review"
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 0)

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.apply_completed_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.core.finalize.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", side_effect=["Pending.", "Clean"])
    @patch("claude_auto_review.stop.orchestration.core.finalize.is_review_clean", return_value=True)
    def test_pending_review_autocomplete_clean_file_returns_0(
        self, mock_clean, mock_verdict, mock_auto, mock_prompt, mock_apply, mock_covered
    ):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 0)
        mock_apply.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.record_completed_review")
    @patch("claude_auto_review.stop.orchestration.core.finalize.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.core.finalize.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.core.finalize.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", side_effect=["Pending.", "Not clean."])
    def test_autocomplete_completed_with_findings_blocks_completion(
        self, mock_verdict, mock_auto, mock_prompt, mock_block, mock_record, mock_covered
    ):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)
        mock_block.assert_called_once()
        mock_record.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.core.finalize.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", side_effect=["Pending.", None])
    def test_autocomplete_returns_2_on_pending(self, mock_verdict, mock_auto, mock_prompt, mock_covered):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.record_completed_review")
    @patch("claude_auto_review.stop.orchestration.core.finalize.block_completed_review_findings")
    @patch("claude_auto_review.stop.orchestration.core.finalize._review_has_completed_artifact", side_effect=[False, True])
    @patch("claude_auto_review.stop.orchestration.core.finalize.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.core.finalize.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", side_effect=["Pending.", None])
    def test_autocomplete_with_non_placeholder_review_blocks_with_findings(
        self, mock_verdict, mock_auto, mock_prompt, mock_completed, mock_block, mock_record, mock_covered
    ):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)
        mock_block.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", return_value=None)
    def test_missing_review_file_blocks(self, mock_verdict, mock_covered):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.block_pending_review")
    @patch("claude_auto_review.stop.orchestration.core.finalize.build_review_completion_prompt")
    @patch("claude_auto_review.stop.orchestration.core.finalize.attempt_stop_autocomplete", return_value=MagicMock(status="cli_not_found"))
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", side_effect=["Pending.", None])
    def test_pending_review_blocks(self, mock_verdict, mock_auto, mock_prompt, mock_block_pending, mock_covered):
        mock_block_pending.return_value = 2
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)
        mock_block_pending.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.block_pending_review")
    @patch("claude_auto_review.stop.orchestration.core.finalize.log_event")
    @patch("claude_auto_review.stop.orchestration.core.finalize.build_review_completion_prompt")
    @patch(
        "claude_auto_review.stop.orchestration.core.finalize.attempt_stop_autocomplete",
        side_effect=[
            MagicMock(status="empty_stdout"),
            MagicMock(status="empty_stdout"),
        ],
    )
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", side_effect=["Pending.", None])
    def test_empty_stdout_after_retry_logs_approval_and_returns_0(
        self, mock_verdict, mock_auto, mock_prompt, mock_log, mock_block_pending, mock_covered
    ):
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 0)
        mock_log.assert_any_call(
            Path("/fake"),
            "stop_hook_claude_cli_retry",
            client_id="c",
            reviewId="r1",
        )
        mock_log.assert_any_call(
            Path("/fake"),
            "stop_hook_claude_cli_empty_approved",
            client_id="c",
            reviewId="r1",
        )
        mock_block_pending.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.core.finalize.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.core.finalize.apply_completed_review")
    @patch("claude_auto_review.stop.orchestration.core.finalize.is_review_clean", return_value=True)
    @patch("claude_auto_review.stop.orchestration.core.finalize._read_review_verdict", return_value="Clean")
    @patch("claude_auto_review.stop.orchestration.core.finalize.block_response")
    def test_completed_clean_with_remaining_files_blocks(
        self, mock_block_response, mock_verdict, mock_clean, mock_apply, mock_covered
    ):
        mock_apply.return_value = [EditRecord(timestamp="t", file="still.ts", hash="abc")]
        result = finalize_review_stop(_ctx(), self.resolution)
        self.assertEqual(result, 2)
        mock_block_response.assert_called_once()


if __name__ == "__main__":
    unittest.main()
