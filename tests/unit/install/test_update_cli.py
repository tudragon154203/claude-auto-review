import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import ANY, MagicMock, patch

from claude_auto_review.install.cli.update import main


def _result(args=None, returncode=0, stdout="", stderr=""):
    return CompletedProcess(args or [], returncode, stdout=stdout, stderr=stderr)


class TestUpdateCli(unittest.TestCase):
    @patch("claude_auto_review.install.cli.update.log_event")
    @patch("claude_auto_review.install.cli.update.subprocess.run")
    @patch("claude_auto_review.paths.path_utils.ProjectContext.from_environment")
    def test_update_pulls_checkout_and_reruns_setup(self, mock_ctx, mock_run, mock_log):
        mock_ctx.return_value = MagicMock(project_root=Path("/project"), plugin_root=Path("/repo/claude_auto_review"))
        mock_run.side_effect = [
            _result(stdout="/repo\n"),
            _result(stdout="Already up to date.\n"),
            _result(stdout="Claude Auto Review initialized at /project/.claude/claude-auto-review\n"),
        ]

        with patch("builtins.print") as mock_print:
            result = main()

        self.assertEqual(result, 0)
        self.assertEqual(mock_run.call_args_list[0].args[0][0], "git")
        self.assertEqual(mock_run.call_args_list[0].args[0][3:], ["rev-parse", "--show-toplevel"])
        self.assertEqual(mock_run.call_args_list[1].args[0], ["git", "-C", str(Path("/repo")), "pull", "--ff-only"])
        self.assertEqual(mock_run.call_args_list[2].args[0][1:], ["-m", "claude_auto_review.install.cli.setup"])
        self.assertEqual(mock_run.call_args_list[2].kwargs["cwd"], Path("/project"))
        mock_log.assert_called_once_with(Path("/project"), "update_completed", checkout=str(Path("/repo")))
        mock_print.assert_any_call("Claude Auto Review update completed.")

    @patch("claude_auto_review.install.cli.update.log_event")
    @patch("claude_auto_review.install.cli.update.subprocess.run")
    @patch("claude_auto_review.paths.path_utils.ProjectContext.from_environment")
    def test_update_requires_git_checkout(self, mock_ctx, mock_run, mock_log):
        mock_ctx.return_value = MagicMock(project_root=Path("/project"), plugin_root=Path("/site/claude_auto_review"))
        mock_run.return_value = _result(returncode=128, stderr="not a git repository\n")

        with patch("builtins.print") as mock_print:
            result = main()

        self.assertEqual(result, 1)
        self.assertEqual(mock_run.call_count, 1)
        mock_log.assert_not_called()
        mock_print.assert_any_call("Claude Auto Review update requires a git checkout install.", file=ANY)


if __name__ == "__main__":
    unittest.main()
