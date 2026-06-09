import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.runtime.context import resolve_project_root
from claude_auto_review.runtime.hook_context import build_hook_runtime_context
from tests.unit.state.support import StateTestCase


class TestResolveProjectRoot(unittest.TestCase):
    @patch("claude_auto_review.runtime.context.ProjectContext.from_environment")
    @patch("claude_auto_review.runtime.context.subprocess.run")
    def test_prefers_git_toplevel_for_worktrees(self, mock_run, mock_ctx):
        mock_ctx.return_value = MagicMock(project_root=Path("/worktree/nested"))
        mock_run.return_value = MagicMock(stdout="/worktree\n")

        result = resolve_project_root()

        self.assertEqual(result, Path("/worktree"))
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path("/worktree/nested"),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )

    @patch("claude_auto_review.runtime.context.ProjectContext.from_environment")
    @patch("claude_auto_review.runtime.context.subprocess.run")
    def test_falls_back_to_environment_root_when_git_missing(self, mock_run, mock_ctx):
        mock_ctx.return_value = MagicMock(project_root=Path("/worktree"))
        mock_run.side_effect = FileNotFoundError

        result = resolve_project_root()

        self.assertEqual(result, Path("/worktree"))

    @patch("claude_auto_review.runtime.context.ProjectContext.from_environment")
    @patch("claude_auto_review.runtime.context.subprocess.run")
    def test_falls_back_to_environment_root_when_git_fails(self, mock_run, mock_ctx):
        mock_ctx.return_value = MagicMock(project_root=Path("/worktree"))
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=128, cmd=["git"], stderr="fatal: not a git repository"
        )

        result = resolve_project_root()

        self.assertEqual(result, Path("/worktree"))

    def test_respects_explicit_project_root(self):
        result = resolve_project_root(Path("/explicit"))

        self.assertEqual(result, Path("/explicit"))

    @patch("claude_auto_review.runtime.context.subprocess.run")
    def test_resolves_to_git_toplevel_in_real_worktree(self, mock_run):
        import subprocess as _subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            repo_dir = tmp / "main"
            work_dir = tmp / "feature"
            work_dir.mkdir()

            _subprocess.run(["git", "init", "--bare", str(tmp / "bare.git")], check=True, capture_output=True)
            _subprocess.run(["git", "clone", str(tmp / "bare.git"), str(repo_dir)], check=True, capture_output=True)
            _subprocess.run(
                ["git", "worktree", "add", "-b", "feature-branch", str(work_dir)],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
            (work_dir / "subdir").mkdir(parents=True)
            (work_dir / "subdir" / "f.txt").write_text("hi", encoding="utf-8")

            mock_run.return_value = MagicMock(stdout=str(repo_dir.resolve()) + "\n")

            with patch(
                "claude_auto_review.runtime.context.ProjectContext.from_environment",
                return_value=MagicMock(project_root=work_dir.resolve()),
            ):
                result = resolve_project_root()

            self.assertEqual(result, repo_dir.resolve())


class TestBuildHookRuntimeContext(StateTestCase, unittest.TestCase):
    def test_build_hook_runtime_context_resolves_payload_client_and_settings(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"enabled": False}}),
            encoding="utf-8",
        )

        with patch("claude_auto_review.runtime.hook_context.ProjectContext.from_environment", return_value=MagicMock(project_root=project_root, plugin_root=project_root)):
            ctx = build_hook_runtime_context(json.dumps({"session_id": "session-1"}))

        self.assertEqual(ctx.project_root, project_root)
        self.assertEqual(ctx.client_id, "session-1")
        self.assertFalse(ctx.settings.core.enabled)
        self.assertEqual(ctx.payload["session_id"], "session-1")
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "clients").exists())

    def test_build_hook_runtime_context_can_skip_client_creation(self):
        project_root = self.temp_project()

        with patch("claude_auto_review.runtime.hook_context.ProjectContext.from_environment", return_value=MagicMock(project_root=project_root, plugin_root=project_root)):
            ctx = build_hook_runtime_context(json.dumps({"session_id": "session-1"}), ensure_client=False)

        self.assertEqual(ctx.client_id, "session-1")
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "clients").exists())


if __name__ == "__main__":
    unittest.main()
