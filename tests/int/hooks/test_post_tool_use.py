import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.state.store_read import load_state  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402


class TestPostToolUseHook(HookTestCase, unittest.TestCase):
    def test_post_tool_use_logs_changed_files_and_stop_hook_blocks(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"tool_input": {"file_path": "src/app.ts"}}))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root, "test-session")[0]["file"], "src/app.ts")

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop.returncode, 2)
        self.assertTrue(json.loads(stop.stdout)["block"])

    def test_post_tool_use_accepts_absolute_file_paths(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": str(target)}))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root, "test-session")[0]["file"], "src/app.ts")

    def test_post_tool_use_tracks_removed_file_and_stop_hook_blocks(self):
        project_root = self.temp_project()
        payload = {"tool_name": "Remove", "tool_input": {"file_path": "src/deleted.ts"}}

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps(payload))
        self.assertEqual(post.returncode, 0)
        state = load_state(project_root, "test-session")
        self.assertEqual(state[0]["file"], "src/deleted.ts")
        self.assertEqual(state[0]["hash"], "__deleted__")
        self.assertFalse(state[0]["reviewed"])
        self.assertTrue(state[0]["deleted"])
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False).returncode, 2)

    def test_post_tool_use_ignores_paths_outside_project(self):
        project_root = self.temp_project()
        outside = Path(tempfile.mkdtemp(prefix="claude-auto-review-outside-")) / "outside.ts"
        outside.write_text("export const outside = true;\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": str(outside)}))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root, "test-session"), [])

    def test_fails_open_for_invalid_hook_input(self):
        project_root = self.temp_project()
        post = self.run_python("hooks/post_tool_use.py", project_root, "{not-json")
        self.assertEqual(post.returncode, 0)

    def test_does_not_track_files_skipped_by_extension(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"skipExtensions": [".MD"]}}),
            encoding="utf-8",
        )
        (project_root / "README.md").write_text("# docs\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "README.md"}))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root, "test-session"), [])
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

    def test_does_not_track_files_outside_include_extension_allowlist(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"includeExtensions": ["py"]}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        (project_root / "src" / "app.py").write_text("value = 1\n", encoding="utf-8")

        ts_post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        py_post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.py"}))
        self.assertEqual(ts_post.returncode, 0)
        self.assertEqual(py_post.returncode, 0)
        self.assertEqual([entry["file"] for entry in load_state(project_root, "test-session")], ["src/app.py"])

    def test_post_tool_use_writes_lifecycle_log_without_stdout(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(post.stdout, "")
        log_path = project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log"
        self.assertIn('"event":"file_tracked"', log_path.read_text(encoding="utf-8"))

    def test_allows_stop_when_disabled_in_project_settings(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"enabled": False}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root, "test-session"), [])
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

    def test_tracks_multiple_files_from_multiedit_style_payload(self):
        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("export const b = 1;\n", encoding="utf-8")
        payload = {"tool_input": {"edits": [{"file_path": "src/a.ts"}, {"file_path": "src/b.ts"}]}}
        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps(payload))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(
            sorted(entry["file"] for entry in load_state(project_root, "test-session")),
            ["src/a.ts", "src/b.ts"],
        )
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False).returncode, 2)


if __name__ == "__main__":
    unittest.main()

