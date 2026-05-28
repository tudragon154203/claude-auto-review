import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.review.prompting.diff_mode import (  # noqa: E402
    client_snapshots_dir,
    snapshot_path_for,
)
from tests.int.hooks.support import HookTestCase  # noqa: E402


def _git_init_and_commit(project_root, files):
    """Initialize a git repo in project_root, add and commit the given files."""
    subprocess.run(["git", "init", "-b", "main"], cwd=project_root, capture_output=True, check=True)
    for f in files:
        full = project_root / f
        subprocess.run(["git", "add", f], cwd=project_root, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline", "--allow-empty"],
        cwd=project_root,
        capture_output=True,
        check=True,
    )


class TestSnapshotCaptureOnFirstEdit(HookTestCase, unittest.TestCase):
    def setUp(self):
        super().setUp()

    def test_snapshot_written_on_first_edit(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 42;\n", encoding="utf-8")
        _git_init_and_commit(project_root, ["src/app.ts"])

        (project_root / "src" / "app.ts").write_text("export const value = 99;\n", encoding="utf-8")
        post = self.run_python(
            "hooks/post_tool_use.py", project_root, json.dumps({"tool_input": {"file_path": "src/app.ts"}})
        )
        self.assertEqual(post.returncode, 0)
        snapshot = snapshot_path_for("src/app.ts", client_snapshots_dir(project_root, "test-session"))
        self.assertTrue(snapshot.exists())
        self.assertIn("value = 42", snapshot.read_text(encoding="utf-8"))

    def test_second_edit_does_not_overwrite_snapshot(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 10;\n", encoding="utf-8")
        _git_init_and_commit(project_root, ["src/app.ts"])

        (project_root / "src" / "app.ts").write_text("export const value = 20;\n", encoding="utf-8")
        post1 = self.run_python(
            "hooks/post_tool_use.py", project_root, json.dumps({"tool_input": {"file_path": "src/app.ts"}})
        )
        self.assertEqual(post1.returncode, 0)

        snapshot = snapshot_path_for("src/app.ts", client_snapshots_dir(project_root, "test-session"))
        first_content = snapshot.read_text(encoding="utf-8")

        (project_root / "src" / "app.ts").write_text("export const value = 30;\n", encoding="utf-8")
        post2 = self.run_python(
            "hooks/post_tool_use.py", project_root, json.dumps({"tool_input": {"file_path": "src/app.ts"}})
        )
        self.assertEqual(post2.returncode, 0)
        self.assertEqual(snapshot.read_text(encoding="utf-8"), first_content)


class TestSnapshotCaptureSkipsRuntime(HookTestCase, unittest.TestCase):
    def test_does_not_snapshot_runtime_paths(self):
        project_root = self.temp_project()
        runtime_file = (
            project_root
            / ".claude" / "claude-auto-review" / "clients" / "test-session" / "state.jsonl"
        )
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text('{"type":"test"}\n', encoding="utf-8")

        post = self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            json.dumps({"file_path": str(runtime_file)}),
        )
        self.assertEqual(post.returncode, 0)
        snapshots_dir = client_snapshots_dir(project_root, "test-session")
        self.assertEqual(list(snapshots_dir.glob("*.snap")), [])


class TestSnapshotCaptureRespectsFilters(HookTestCase, unittest.TestCase):
    def test_skip_extensions_still_skip_snapshot(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"skipExtensions": [".md"]}}),
            encoding="utf-8",
        )
        (project_root / "README.md").write_text("# docs\n", encoding="utf-8")
        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "README.md"}))
        self.assertEqual(post.returncode, 0)
        snapshots_dir = client_snapshots_dir(project_root, "test-session")
        self.assertEqual(list(snapshots_dir.glob("*.snap")), [])

    def test_include_extensions_filter_applies_before_snapshot(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("const x = 1;\n", encoding="utf-8")
        (project_root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        _git_init_and_commit(project_root, ["src/app.ts", "src/app.py"])

        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"includeExtensions": [".py"]}}),
            encoding="utf-8",
        )

        (project_root / "src" / "app.ts").write_text("const x = 2;\n", encoding="utf-8")
        (project_root / "src" / "app.py").write_text("x = 2\n", encoding="utf-8")

        ts_post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        py_post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.py"}))
        self.assertEqual(ts_post.returncode, 0)
        self.assertEqual(py_post.returncode, 0)

        snapshots_dir = client_snapshots_dir(project_root, "test-session")
        snap_files = list(snapshots_dir.glob("*.snap"))
        self.assertEqual(len(snap_files), 1)
        self.assertIn("src_app.py", str(snap_files[0]))


class TestDeletedFileNoSnapshot(HookTestCase, unittest.TestCase):
    def test_deleted_file_does_not_produce_snapshot(self):
        project_root = self.temp_project()
        payload = {"tool_name": "Remove", "tool_input": {"file_path": "src/deleted.ts"}}
        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps(payload))
        self.assertEqual(post.returncode, 0)
        snapshots_dir = client_snapshots_dir(project_root, "test-session")
        self.assertEqual(list(snapshots_dir.glob("*.snap")), [])
