import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.reviews.prompt.runner import (
    _block_review_prompt_failure,
    _reload_client_state,
    _review_prompt_command,
    _review_prompt_path,
    run_review_prompt,
)
from tests.support_paths import FAKE_ROOT


def _ctx(project_root=FAKE_ROOT, client_id="client-1"):
    return RuntimeContext(project_root=project_root, client_id=client_id)


class TestPromptRunner(unittest.TestCase):
    def test_review_prompt_command_uses_current_python(self):
        self.assertEqual(
            _review_prompt_command(Path("/fake/script.py")), [sys.executable, str(Path("/fake/script.py"))]
        )

    @patch("claude_auto_review.stop.reviews.prompt.runner.client_run_dir", return_value=Path("/fake/run"))
    def test_review_prompt_path_uses_client_run_dir(self, mock_client_run_dir):
        self.assertEqual(_review_prompt_path(_ctx(), "r1"), Path("/fake/run/review-r1-prompt.md"))

    @patch("claude_auto_review.stop.reviews.prompt.runner.log_event")
    @patch("claude_auto_review.stop.reviews.prompt.runner.run_captured")
    def test_run_review_prompt_logs_and_returns_result(self, mock_run, mock_log):
        mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        env = {"CLAUDE_SESSION_ID": "sid"}
        result = run_review_prompt(_ctx(), Path("/fake/prompt.py"), env)

        self.assertEqual(result.returncode, 0)
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 60)
        self.assertEqual(mock_run.call_args.kwargs["env"], env)
        mock_log.assert_called_once_with(
            FAKE_ROOT,
            "stop_hook_review_invoked",
            client_id="client-1",
            stdout="ok",
            stderr="",
            returncode=0,
        )

    def test_block_review_prompt_failure_formats_message(self):
        result = MagicMock(stdout="stdout text", stderr="stderr text")
        emitter = MagicMock()

        _block_review_prompt_failure("a.ts", result, emitter=emitter)

        emitter.block.assert_called_once()
        self.assertIn("Failed to create review for a.ts.", emitter.block.call_args.args[0])
        self.assertIn("stdout text", emitter.block.call_args.args[1])
        self.assertIn("stderr text", emitter.block.call_args.args[1])

    @patch("claude_auto_review.stop.reviews.prompt.runner.get_unreviewed_files", return_value=[{"file": "a.ts"}])
    @patch("claude_auto_review.stop.reviews.prompt.runner.load_state_snapshot")
    def test_reload_client_state_returns_state_and_unreviewed(self, mock_load_snapshot, mock_get_unreviewed):
        mock_snapshot = MagicMock()
        mock_snapshot.events = [{"type": "edit"}]
        mock_load_snapshot.return_value = mock_snapshot
        state, unreviewed = _reload_client_state(_ctx())
        self.assertEqual(state, [{"type": "edit"}])
        self.assertEqual(unreviewed, [{"file": "a.ts"}])


if __name__ == "__main__":
    unittest.main()
