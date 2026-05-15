import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.state.core.models import EditRecord, ReviewMetadata
from claude_auto_review.stop.orchestration.core.context import RuntimeContext
from claude_auto_review.stop.orchestration.core.pending import resolve_pending_review

from tests.unit.state.support import StateTestCase


def _mk_edit(file: str = "a.py", hash: str = "h1") -> EditRecord:
    return EditRecord(timestamp="2026-05-11T10:00:00+07:00", file=file, hash=hash)


def _mk_review(reviewId: str = "r1") -> ReviewMetadata:
    return ReviewMetadata(
        timestamp="2026-05-11T10:00:00+07:00",
        reviewId=reviewId,
        reviewPath="/fake/r.md",
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


class TestResolvePendingReview(unittest.TestCase):
    base_kwargs = {
        "state": [],
        "unreviewed": [_mk_edit()],
        "timeout_hours": 1,
        "review_prompt_script": Path("/fake/script"),
    }

    @patch("claude_auto_review.stop.orchestration.core.pending.find_pending_review_for_files")
    @patch("claude_auto_review.stop.orchestration.core.pending._run_review_prompt")
    def test_existing_pending_review_returns_review(self, mock_run, mock_find):
        review = _mk_review()
        mock_find.return_value = review
        result = resolve_pending_review(_ctx(), **self.base_kwargs)
        self.assertEqual(result.review, review)
        self.assertFalse(result.is_terminal)
        mock_run.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.core.pending.find_pending_review_for_files", return_value=None)
    @patch("claude_auto_review.stop.orchestration.core.pending._run_review_prompt")
    def test_no_pending_runs_prompt(self, mock_run, mock_find):
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        result = resolve_pending_review(_ctx(), **self.base_kwargs)
        mock_run.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.core.pending.find_pending_review_for_files")
    @patch("claude_auto_review.stop.orchestration.core.pending._run_review_prompt", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=60))
    def test_timeout_blocks_stop(self, mock_run, mock_find):
        mock_find.return_value = None
        result = resolve_pending_review(_ctx(), **self.base_kwargs)
        self.assertEqual(result.exit_code, 2)

    @patch("claude_auto_review.stop.orchestration.core.pending.find_pending_review_for_files")
    @patch("claude_auto_review.stop.orchestration.core.pending._run_review_prompt", side_effect=OSError("boom"))
    def test_error_blocks_stop(self, mock_run, mock_find):
        mock_find.return_value = None
        result = resolve_pending_review(_ctx(), **self.base_kwargs)
        self.assertEqual(result.exit_code, 2)

    @patch("claude_auto_review.stop.orchestration.core.pending._reload_client_state")
    @patch("claude_auto_review.stop.orchestration.core.pending.find_pending_review_for_files")
    @patch("claude_auto_review.stop.orchestration.core.pending._run_review_prompt")
    @patch("claude_auto_review.stop.orchestration.core.pending._block_review_prompt_failure")
    def test_prompt_runs_but_no_review_created_blocks(self, mock_block, mock_run, mock_find, mock_reload):
        mock_find.return_value = None
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        mock_reload.return_value = ([], [_mk_edit()])
        mock_find_second = mock_find
        mock_find_second.return_value = None

        result = resolve_pending_review(_ctx(), **self.base_kwargs)
        self.assertEqual(result.exit_code, 2)
        mock_block.assert_called_once()


if __name__ == "__main__":
    unittest.main()
