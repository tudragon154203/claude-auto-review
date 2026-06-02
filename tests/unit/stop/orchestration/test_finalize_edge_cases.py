import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.support_paths import FAKE_ROOT

from claude_auto_review.config.constants.exit_codes import EXIT_REVIEW_FAILED
from claude_auto_review.config.settings.models import PluginSettings
from claude_auto_review.state.records.edit import EditRecord
from claude_auto_review.state.records.review import ReviewMetadata
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.orchestration.deps import build_default_eval_deps
from claude_auto_review.stop.orchestration.finalize.core import finalize_review_stop
from claude_auto_review.stop.orchestration.types.resolution import ReviewResolution


def _mk_review(reviewId: str = "r1", reviewPath: str = "/fake/r.md") -> ReviewMetadata:
    return ReviewMetadata(
        timestamp="2026-05-11T10:00:00+07:00",
        reviewId=reviewId,
        reviewPath=reviewPath,
        files=[],
        clientId="c",
        status="pending",
    )


def _ctx(project_root=FAKE_ROOT, client_id="c", settings=None, payload=None):
    return RuntimeContext(
        project_root=project_root,
        client_id=client_id,
        settings=settings or PluginSettings(),
        payload=payload if payload is not None else {},
    )


def _mock_emitter():
    return MagicMock()


class TestFinalizeEdgeCases(unittest.TestCase):
    def setUp(self):
        self.resolution = ReviewResolution(
            state=[],
            unreviewed=[],
            review=_mk_review("r1"),
        )

    @patch("claude_auto_review.stop.orchestration.finalize.core.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.core.block_pending_review")
    def test_missing_review_file_blocks(self, mock_block_pending, mock_covered):
        mock_classify = MagicMock(side_effect=[MagicMock(status="pending"), MagicMock(status="pending")])
        emitter = _mock_emitter()
        result = finalize_review_stop(_ctx(), self.resolution, deps=build_default_eval_deps(emitter=emitter, state_event_writer_factory=MagicMock(), classify_fn=mock_classify))
        self.assertEqual(result, EXIT_REVIEW_FAILED)

    @patch("claude_auto_review.stop.orchestration.finalize.core.get_entries_covered_by_review", return_value=[])
    def test_invalid_reviewer_backend_blocks_instead_of_approving(
        self, mock_covered
    ):
        emitter = _mock_emitter()
        mock_log = MagicMock()
        result = finalize_review_stop(
            _ctx(settings=PluginSettings.from_mapping({"reviewerBackend": "codyx"})),
            self.resolution,
            deps=build_default_eval_deps(emitter=emitter, state_event_writer_factory=MagicMock(), log_event_fn=mock_log),
        )
        self.assertEqual(result, EXIT_REVIEW_FAILED)
        emitter.block.assert_called_once_with(
            "Claude Auto Review: invalid reviewerBackend setting",
            "Unsupported reviewer backend: codyx",
        )
        mock_log.assert_any_call(
            FAKE_ROOT,
            "stop_hook_invalid_reviewer_backend",
            client_id="c",
            error="Unsupported reviewer backend: codyx",
        )

    @patch("claude_auto_review.stop.orchestration.finalize.core.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.core.block_pending_review")
    @patch("claude_auto_review.stop.orchestration.finalize.autocomplete.build_review_completion_prompt")
    @patch(
        "claude_auto_review.stop.orchestration.finalize.autocomplete.attempt_stop_autocomplete",
        side_effect=[
            MagicMock(status="empty_stdout"),
            MagicMock(status="empty_stdout"),
        ],
    )
    def test_empty_stdout_after_retry_blocks_pending_review(
        self, mock_auto, mock_prompt, mock_block_pending, mock_covered
    ):
        mock_classify = MagicMock(side_effect=[MagicMock(status="pending"), MagicMock(status="pending")])
        mock_block_pending.return_value = EXIT_REVIEW_FAILED
        emitter = _mock_emitter()
        mock_log = MagicMock()
        result = finalize_review_stop(
            _ctx(), self.resolution,
            deps=build_default_eval_deps(emitter=emitter, state_event_writer_factory=MagicMock(), log_event_fn=mock_log, classify_fn=mock_classify),
        )
        self.assertEqual(result, EXIT_REVIEW_FAILED)
        mock_log.assert_any_call(
            FAKE_ROOT,
            "stop_hook_reviewer_retry",
            client_id="c",
            reviewId="r1",
        )
        mock_log.assert_any_call(
            FAKE_ROOT,
            "stop_hook_reviewer_empty_blocked",
            client_id="c",
            reviewId="r1",
        )
        mock_block_pending.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.finalize.core.get_entries_covered_by_review", return_value=[])
    @patch("claude_auto_review.stop.orchestration.finalize.plan_executor.apply_completed_review")
    def test_completed_clean_with_remaining_files_blocks(
        self, mock_apply, mock_covered
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            review_dir = project_root / "fake"
            review_dir.mkdir(parents=True, exist_ok=True)
            review_path = review_dir / "r.md"
            review_path.write_text(
                "## Verdict\nClean - no issues found. Claude may stop.\n",
                encoding="utf-8",
            )
            mock_apply.return_value = [EditRecord(timestamp="t", file="still.ts", hash="abc")]
            resolution = ReviewResolution(state=[], unreviewed=[], review=_mk_review("r1", "fake/r.md"))
            emitter = _mock_emitter()
            result = finalize_review_stop(_ctx(project_root=project_root), resolution, deps=build_default_eval_deps(emitter=emitter, state_event_writer_factory=MagicMock()))
            self.assertEqual(result, EXIT_REVIEW_FAILED)
            emitter.block.assert_called_once()


if __name__ == "__main__":
    unittest.main()
