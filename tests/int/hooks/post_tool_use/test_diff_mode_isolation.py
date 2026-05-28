import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.review.prompting.diff_mode import (  # noqa: E402
    all_session_diffs,
    capture_session_snapshot,
    client_snapshots_dir,
    session_scoped_diff,
    snapshot_path_for,
)
from tests.int.hooks.support import HookTestCase  # noqa: E402


def _git_init_and_commit(project_root, files):
    subprocess.run(["git", "init", "-b", "main"], cwd=project_root, capture_output=True, check=True)
    for file_path in files:
        subprocess.run(["git", "add", file_path], cwd=project_root, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "baseline", "--allow-empty"], cwd=project_root, capture_output=True, check=True)


def _git_commit_all(project_root, message):
    subprocess.run(["git", "add", "-A"], cwd=project_root, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=project_root, capture_output=True, check=True)


class TestSessionDiffClientIsolation(HookTestCase, unittest.TestCase):
    def _setup_shared_repo(self):
        project_root = self.temp_project()
        shared_file = project_root / "src" / "app.py"
        shared_file.parent.mkdir(parents=True, exist_ok=True)
        shared_file.write_text("value = 1\n", encoding="utf-8")
        _git_init_and_commit(project_root, ["src/app.py"])
        return project_root, "src/app.py"

    def test_clients_use_independent_snapshots(self):
        project_root, file_path = self._setup_shared_repo()
        shared = project_root / file_path

        shared.write_text("value = 1\nother_dev_line = True\n", encoding="utf-8")
        _git_commit_all(project_root, "other dev adds line")

        capture_session_snapshot(file_path, project_root, "client-a")
        shared.write_text("value = 1\nother_dev_line = True\nclient_a_line = True\n", encoding="utf-8")

        capture_session_snapshot(file_path, project_root, "client-b")
        shared.write_text("value = 1\nother_dev_line = True\nclient_b_line = True\n", encoding="utf-8")

        diff_a = session_scoped_diff(file_path, project_root, "client-a")
        diff_b = session_scoped_diff(file_path, project_root, "client-b")

        self.assertIn("+client_b_line = True", diff_a)
        self.assertIn("+client_b_line = True", diff_b)
        self.assertNotIn("+other_dev_line = True", diff_a)
        self.assertNotIn("+other_dev_line = True", diff_b)

    def test_snapshots_live_in_separate_client_directories(self):
        project_root, file_path = self._setup_shared_repo()
        shared = project_root / file_path

        shared.write_text("value = 10\n", encoding="utf-8")
        capture_session_snapshot(file_path, project_root, "client-x")

        shared.write_text("value = 20\n", encoding="utf-8")
        _git_commit_all(project_root, "update to 20")
        capture_session_snapshot(file_path, project_root, "client-y")

        snap_x = snapshot_path_for(file_path, client_snapshots_dir(project_root, "client-x"))
        snap_y = snapshot_path_for(file_path, client_snapshots_dir(project_root, "client-y"))

        self.assertIn("value = 1", snap_x.read_text(encoding="utf-8"))
        self.assertIn("value = 20", snap_y.read_text(encoding="utf-8"))
        self.assertNotEqual(snap_x.parent, snap_y.parent)

    def test_all_session_diffs_uses_per_client_snapshot(self):
        project_root, file_path = self._setup_shared_repo()
        shared = project_root / file_path

        shared.write_text("value = 10\n", encoding="utf-8")
        capture_session_snapshot(file_path, project_root, "alpha")

        shared.write_text("value = 20\n", encoding="utf-8")
        _git_commit_all(project_root, "update to 20")
        capture_session_snapshot(file_path, project_root, "beta")

        shared.write_text("value = 20\nbeta_line = True\n", encoding="utf-8")

        result_a = all_session_diffs([file_path], project_root, "alpha")
        result_b = all_session_diffs([file_path], project_root, "beta")

        self.assertIn("+value = 20", result_a)
        self.assertIn("+beta_line = True", result_a)
        self.assertIn("+beta_line = True", result_b)

    def test_hook_captures_each_clients_snapshot_independently(self):
        project_root, file_path = self._setup_shared_repo()
        shared = project_root / file_path

        shared.write_text("value = 10\n", encoding="utf-8")
        post_a = self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            json.dumps({"tool_input": {"file_path": file_path}}),
            client_id="e2e-client-a",
        )
        self.assertEqual(post_a.returncode, 0)

        _git_commit_all(project_root, "client a edit")

        shared.write_text("value = 20\n", encoding="utf-8")
        post_b = self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            json.dumps({"tool_input": {"file_path": file_path}}),
            client_id="e2e-client-b",
        )
        self.assertEqual(post_b.returncode, 0)

        snap_a = snapshot_path_for(file_path, client_snapshots_dir(project_root, "e2e-client-a"))
        snap_b = snapshot_path_for(file_path, client_snapshots_dir(project_root, "e2e-client-b"))

        self.assertIn("value = 1", snap_a.read_text(encoding="utf-8"))
        self.assertIn("value = 10", snap_b.read_text(encoding="utf-8"))
