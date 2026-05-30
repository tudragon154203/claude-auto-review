import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.state.store.read import load_state  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402


class TestPostToolUseHook(HookTestCase, unittest.TestCase):
    def test_post_tool_use_logs_changed_files_and_stop_hook_blocks(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        post = self.run_python(
            "hooks/post_tool_use.py", project_root, json.dumps({"tool_input": {"file_path": "src/app.ts"}})
        )
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root, "test-session")[0].file, "src/app.ts")

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop.returncode, 2)
        self.assertEqual(json.loads(stop.stdout)["decision"], "block")

    def test_post_tool_use_accepts_absolute_file_paths(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": str(target)}))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root, "test-session")[0].file, "src/app.ts")

    def test_post_tool_use_accepts_canonical_file_uris(self):
        project_root = self.temp_project()
        target = (project_root / "src" / "app.ts").resolve()
        target.write_text("export const value = 1;\n", encoding="utf-8")

        post = self.run_python(
            "hooks/post_tool_use.py", project_root, json.dumps({"file_path": f"file:///{target.as_posix()}"})
        )
        self.assertEqual(post.returncode, 0)
        state = load_state(project_root, "test-session")
        self.assertEqual(state[0].file, "src/app.ts")
        self.assertNotEqual(state[0].hash, "__deleted__")

    def test_post_tool_use_tracks_removed_file_and_stop_hook_allows(self):
        project_root = self.temp_project()
        payload = {"tool_name": "Remove", "tool_input": {"file_path": "src/deleted.ts"}}

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps(payload))
        self.assertEqual(post.returncode, 0)
        state = load_state(project_root, "test-session")
        self.assertEqual(state[0].file, "src/deleted.ts")
        self.assertEqual(state[0].hash, "__deleted__")
        self.assertFalse(state[0].reviewed)
        self.assertTrue(state[0].deleted)
        self.assertEqual(
            self.run_python(
                "hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False
            ).returncode,
            0,
        )

    def test_post_tool_use_ignores_paths_outside_project(self):
        project_root = self.temp_project()
        with tempfile.TemporaryDirectory(prefix="claude-auto-review-outside-") as tmpdir:
            outside = Path(tmpdir) / "outside.ts"
            outside.write_text("export const outside = true;\n", encoding="utf-8")

            post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": str(outside)}))
            self.assertEqual(post.returncode, 0)
            self.assertEqual(load_state(project_root, "test-session"), [])

    def test_post_tool_use_ignores_runtime_review_files(self):
        project_root = self.temp_project()
        from claude_auto_review.runtime.client_dirs import get_client_id, get_client_runtime_dir

        cid = get_client_id(stdin_session_id="test-session")
        runtime_review = get_client_runtime_dir(project_root, cid) / "reviews" / "review-r1.md"
        runtime_review.parent.mkdir(parents=True, exist_ok=True)
        runtime_review.write_text("## Verdict\nPending.\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": str(runtime_review)}))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root, "test-session"), [])

    def test_fails_open_for_invalid_hook_input(self):
        project_root = self.temp_project()
        post = self.run_python("hooks/post_tool_use.py", project_root, "{not-json")
        self.assertEqual(post.returncode, 0)

    def test_tracks_multiple_files_from_multiedit_style_payload(self):
        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("export const b = 1;\n", encoding="utf-8")
        payload = {"tool_input": {"edits": [{"file_path": "src/a.ts"}, {"file_path": "src/b.ts"}]}}
        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps(payload))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(
            sorted(entry.file for entry in load_state(project_root, "test-session")),
            ["src/a.ts", "src/b.ts"],
        )
        self.assertEqual(
            self.run_python(
                "hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False
            ).returncode,
            2,
        )

    def test_tracks_shell_move_source_deletion_and_destination_edit(self):
        project_root = self.temp_project()
        new_path = project_root / "src" / "new.ts"
        new_path.write_text("export const renamed = true;\n", encoding="utf-8")
        payload = {"tool_name": "Bash", "tool_input": {"command": "mv src/old.ts src/new.ts"}}

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps(payload))

        self.assertEqual(post.returncode, 0)
        state = load_state(project_root, "test-session")
        self.assertEqual([entry.file for entry in state], ["src/old.ts", "src/new.ts"])
        self.assertEqual(state[0].hash, "__deleted__")
        self.assertTrue(state[0].deleted)
        self.assertNotEqual(state[1].hash, "__deleted__")
        self.assertFalse(state[1].deleted)
        self.assertEqual(
            self.run_python(
                "hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False
            ).returncode,
            2,
        )

    def test_tracks_shell_move_into_existing_directory_as_destination_file(self):
        project_root = self.temp_project()
        new_path = project_root / "dst" / "old.ts"
        new_path.parent.mkdir()
        new_path.write_text("export const moved = true;\n", encoding="utf-8")
        payload = {"tool_name": "Bash", "tool_input": {"command": "mv src/old.ts dst"}}

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps(payload))

        self.assertEqual(post.returncode, 0)
        state = load_state(project_root, "test-session")
        self.assertEqual([entry.file for entry in state], ["src/old.ts", "dst/old.ts"])
        self.assertEqual(state[0].hash, "__deleted__")
        self.assertTrue(state[0].deleted)
        self.assertNotEqual(state[1].hash, "__deleted__")
        self.assertFalse(state[1].deleted)

    def test_tracks_multi_source_shell_move_into_directory(self):
        project_root = self.temp_project()
        for name in ("a.ts", "b.ts"):
            target = project_root / "dst" / name
            target.parent.mkdir(exist_ok=True)
            target.write_text(f"export const {name[0]} = true;\n", encoding="utf-8")
        payload = {"tool_name": "Bash", "tool_input": {"command": "mv src/a.ts src/b.ts dst"}}

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps(payload))

        self.assertEqual(post.returncode, 0)
        state = load_state(project_root, "test-session")
        self.assertEqual(
            [entry.file for entry in state],
            ["src/a.ts", "src/b.ts", "dst/a.ts", "dst/b.ts"],
        )
        self.assertEqual([entry.deleted for entry in state], [True, True, False, False])


if __name__ == "__main__":
    unittest.main()
