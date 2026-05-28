import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.review.prompting.diff_mode import (
    all_session_diffs,
    capture_session_snapshot,
    client_snapshots_dir,
    session_scoped_diff,
    snapshot_path_for,
)


class TestSnapshotPathFor(unittest.TestCase):
    def test_mangles_nested_relative_path(self):
        snapshots_dir = Path("/tmp/snapshots")
        self.assertEqual(snapshot_path_for("src/app/main.py", snapshots_dir), snapshots_dir / "src_app_main.py.snap")

    def test_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            snapshot_path_for("../secret.txt", Path("/tmp/snapshots"))

    def test_rejects_absolute_path(self):
        with self.assertRaises(ValueError):
            snapshot_path_for("/etc/passwd", Path("/tmp/snapshots"))


class TestClientSnapshotsDir(unittest.TestCase):
    def test_creates_and_returns_snapshots_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            with patch("claude_auto_review.runtime.client_dirs.datetime") as fake_datetime:
                fake_datetime.now.return_value.strftime.return_value = "20260528-091706"
                result = client_snapshots_dir(project_root, "test-session")
            self.assertTrue(result.exists())
            self.assertTrue(result.is_dir())
            self.assertEqual(
                result,
                project_root
                / ".claude"
                / "claude-auto-review"
                / "clients"
                / "client-20260528-091706_test-session"
                / "snapshots",
            )


class TestCaptureSessionSnapshot(unittest.TestCase):
    def test_writes_snapshot_from_git_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            with patch("claude_auto_review.review.prompting.diff_mode.run_captured") as run_captured:
                run_captured.return_value.stdout = "baseline content\n"
                run_captured.return_value.stderr = ""
                run_captured.return_value.returncode = 0
                result = capture_session_snapshot("src/app.py", project_root, "test-session")
            self.assertTrue(result)
            snapshot_file = client_snapshots_dir(project_root, "test-session") / "src_app.py.snap"
            self.assertEqual(snapshot_file.read_text(encoding="utf-8"), "baseline content\n")

    def test_is_idempotent_once_snapshot_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            snapshot_file = client_snapshots_dir(project_root, "test-session") / "src_app.py.snap"
            snapshot_file.write_text("existing baseline", encoding="utf-8")
            with patch("claude_auto_review.review.prompting.diff_mode.run_captured") as run_captured:
                result = capture_session_snapshot("src/app.py", project_root, "test-session")
            self.assertTrue(result)
            run_captured.assert_not_called()
            self.assertEqual(snapshot_file.read_text(encoding="utf-8"), "existing baseline")

    def test_returns_false_when_git_baseline_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            with patch("claude_auto_review.review.prompting.diff_mode.run_captured") as run_captured:
                run_captured.side_effect = FileNotFoundError()
                result = capture_session_snapshot("src/app.py", project_root, "test-session")
            self.assertFalse(result)


class TestSessionScopedDiff(unittest.TestCase):
    def test_returns_diff_against_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            snapshots_dir = client_snapshots_dir(project_root, "test-session")
            (project_root / "src").mkdir(parents=True, exist_ok=True)
            (project_root / "src" / "app.py").write_text("print('new')\n", encoding="utf-8")
            (snapshots_dir / "src_app.py.snap").write_text("print('old')\n", encoding="utf-8")
            diff = session_scoped_diff("src/app.py", project_root, "test-session")
            self.assertIn("-print('old')", diff)
            self.assertIn("+print('new')", diff)

    def test_returns_file_content_when_snapshot_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "src").mkdir(parents=True, exist_ok=True)
            (project_root / "src" / "app.py").write_text("print('new')\n", encoding="utf-8")
            diff = session_scoped_diff("src/app.py", project_root, "test-session")
            self.assertIn("print('new')", diff)

    def test_returns_deletion_message_when_snapshot_missing_and_file_gone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            diff = session_scoped_diff("src/gone.py", project_root, "test-session")
            self.assertEqual(diff, "File does not currently exist.")


class TestAllSessionDiffs(unittest.TestCase):
    def test_combines_multiple_file_diffs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            snapshots_dir = client_snapshots_dir(project_root, "test-session")
            (project_root / "a.py").write_text("a2\n", encoding="utf-8")
            (project_root / "b.py").write_text("b2\n", encoding="utf-8")
            (snapshots_dir / "a.py.snap").write_text("a1\n", encoding="utf-8")
            (snapshots_dir / "b.py.snap").write_text("b1\n", encoding="utf-8")
            result = all_session_diffs(["a.py", "b.py"], project_root, "test-session")
            self.assertIn("## a.py", result)
            self.assertIn("## b.py", result)
            self.assertIn("-a1", result)
            self.assertIn("+a2", result)
            self.assertIn("-b1", result)
            self.assertIn("+b2", result)
