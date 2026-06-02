import subprocess
import unittest
from unittest.mock import MagicMock, patch

from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.records.review import ReviewMetadata
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.orchestration.finalize.pending import resolve_pending_review
from claude_auto_review.stop.orchestration.types.resolution import ReviewResolution
from tests.support_paths import FAKE_ROOT


def _mk_edit(file: str = "a.py", hash: str = "h1") -> EditRecord:
    return EditRecord(timestamp="2026-05-11T10:00:00+07:00", file=file, hash=hash)


def _mk_review(reviewId: str = "r1") -> ReviewMetadata:
    return ReviewMetadata(
        timestamp="2026-05-11T10:00:00+07:00",
        reviewId=reviewId,
        reviewPath=str(FAKE_ROOT / "r.md"),
        files=[],
        clientId="c",
        status="pending",
    )


def _ctx(project_root=FAKE_ROOT, client_id="c", settings=None, payload=None):
    return RuntimeContext(
        project_root=project_root,
        client_id=client_id,
        settings=settings if settings is not None else {},
        payload=payload if payload is not None else {},
    )


def _mock_emitter():
    return MagicMock()


class TestResolvePendingReview(unittest.TestCase):
    base_kwargs = {
        "state": [],
        "unreviewed": [_mk_edit()],
        "timeout_hours": 1,
        "review_prompt_script": FAKE_ROOT / "script",
    }

    @patch("claude_auto_review.stop.orchestration.finalize.pending.best_pending_review_exactly_matching_entries")
    @patch("claude_auto_review.stop.orchestration.finalize.review_executor.run_review_prompt")
    def test_existing_pending_review_returns_review(self, mock_run, mock_find):
        review = _mk_review()
        mock_find.return_value = review
        emitter = _mock_emitter()
        result = resolve_pending_review(_ctx(), **self.base_kwargs, emitter=emitter)
        self.assertIsInstance(result, ReviewResolution)
        self.assertEqual(result.review, review)
        mock_run.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.finalize.pending.best_pending_review_exactly_matching_entries", return_value=None)
    @patch("claude_auto_review.stop.orchestration.finalize.review_executor.run_review_prompt")
    def test_no_pending_runs_prompt(self, mock_run, mock_find):
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        emitter = _mock_emitter()
        resolve_pending_review(_ctx(), **self.base_kwargs, emitter=emitter)
        mock_run.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.pending.best_pending_review_exactly_matching_entries")
    @patch("claude_auto_review.stop.orchestration.finalize.review_executor.run_review_prompt", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=60))
    def test_timeout_blocks_stop(self, mock_run, mock_find):
        mock_find.return_value = None
        emitter = _mock_emitter()
        result = resolve_pending_review(_ctx(), **self.base_kwargs, emitter=emitter)
        self.assertEqual(result.exit_code, 2)

    @patch("claude_auto_review.stop.orchestration.finalize.pending.best_pending_review_exactly_matching_entries")
    @patch("claude_auto_review.stop.orchestration.finalize.review_executor.run_review_prompt", side_effect=OSError("boom"))
    def test_error_blocks_stop(self, mock_run, mock_find):
        mock_find.return_value = None
        emitter = _mock_emitter()
        result = resolve_pending_review(_ctx(), **self.base_kwargs, emitter=emitter)
        self.assertEqual(result.exit_code, 2)

    @patch("claude_auto_review.stop.orchestration.finalize.review_executor._reload_client_state")
    @patch("claude_auto_review.stop.orchestration.finalize.pending.best_pending_review_exactly_matching_entries")
    @patch("claude_auto_review.stop.orchestration.finalize.review_executor.run_review_prompt")
    @patch("claude_auto_review.stop.orchestration.finalize.review_executor._block_review_prompt_failure")
    def test_prompt_runs_but_no_review_created_blocks(self, mock_block, mock_run, mock_find, mock_reload):
        mock_find.return_value = None
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        mock_reload.return_value = ([], [_mk_edit()])
        mock_find_second = mock_find
        mock_find_second.return_value = None

        emitter = _mock_emitter()
        result = resolve_pending_review(_ctx(), **self.base_kwargs, emitter=emitter)
        self.assertEqual(result.exit_code, 2)
        mock_block.assert_called_once()
        emitter.approve.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.finalize.review_executor._reload_client_state")
    @patch("claude_auto_review.stop.orchestration.finalize.pending.best_pending_review_exactly_matching_entries", return_value=None)
    @patch("claude_auto_review.stop.orchestration.finalize.review_executor.run_review_prompt")
    def test_prompt_can_clear_unreviewed_and_emits_approval_response(self, mock_run, mock_find, mock_reload):
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        mock_reload.return_value = ([], [])

        emitter = _mock_emitter()
        result = resolve_pending_review(_ctx(), **self.base_kwargs, emitter=emitter)

        self.assertEqual(result.exit_code, 0)
        emitter.approve.assert_called_once_with("Claude Auto Review: stop approved (no_unreviewed_files_after_review)")


if __name__ == "__main__":
    unittest.main()
