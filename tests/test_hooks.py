import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.state import append_state, load_state

REPO_ROOT = Path(__file__).resolve().parent.parent


class HookTests(unittest.TestCase):
    def temp_project(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-hooks-"))
        (project_root / "src").mkdir(parents=True)
        return project_root

    def run_python(self, script, project_root, input_text=""):
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_root)}
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / script)],
            cwd=project_root,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def complete_latest_review(self, project_root, verdict="Clean - no issues found. Claude may stop."):
        review_path = sorted((project_root / ".claude" / "claude-auto-review" / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        content = content.replace("Pending. Claude must complete this review from", "Completed review from")
        content = content.replace("Pending.", verdict)
        review_path.write_text(content, encoding="utf-8", newline="\n")
        return review_path

    def test_post_tool_use_logs_changed_files_and_stop_hook_blocks(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"tool_input": {"file_path": "src/app.ts"}}))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root)[0]["file"], "src/app.ts")

        stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop.returncode, 2)
        self.assertTrue(json.loads(stop.stdout)["block"])

    def test_post_tool_use_accepts_absolute_file_paths(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": str(target)}))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root)[0]["file"], "src/app.ts")

    def test_post_tool_use_tracks_removed_file_and_stop_hook_blocks(self):
        project_root = self.temp_project()
        payload = {"tool_name": "Remove", "tool_input": {"file_path": "src/deleted.ts"}}

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps(payload))
        self.assertEqual(post.returncode, 0)
        state = load_state(project_root)
        self.assertEqual(state[0]["file"], "src/deleted.ts")
        self.assertEqual(state[0]["hash"], "__deleted__")
        self.assertFalse(state[0]["reviewed"])
        self.assertTrue(state[0]["deleted"])
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 2)

    def test_post_tool_use_ignores_paths_outside_project(self):
        project_root = self.temp_project()
        outside = Path(tempfile.mkdtemp(prefix="claude-auto-review-outside-")) / "outside.ts"
        outside.write_text("export const outside = true;\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": str(outside)}))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(load_state(project_root), [])

    def test_review_prompt_creates_prompt_and_allows_later_stop(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        review = self.run_python("scripts/review_prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        self.assertEqual(len(list((project_root / ".claude" / "claude-auto-review" / "run").iterdir())), 1)
        self.assertEqual(len(list((project_root / ".claude" / "claude-auto-review" / "reviews").iterdir())), 1)
        pending_stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(pending_stop.returncode, 2)
        self.assertIn("still pending", json.loads(pending_stop.stdout)["message"])
        self.complete_latest_review(project_root)
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

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
        self.assertEqual(load_state(project_root), [])
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
        self.assertEqual([entry["file"] for entry in load_state(project_root)], ["src/app.py"])

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
        self.assertEqual(load_state(project_root), [])
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

    def test_treats_previously_reviewed_identical_hash_as_already_reviewed(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.run_python("scripts/review_prompt.py", project_root)
        self.complete_latest_review(project_root)
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)
        post_again = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(post_again.returncode, 0)
        self.assertTrue(load_state(project_root)[-1]["reviewed"])
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

    def test_reblocks_after_reviewed_file_changes_to_new_hash(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.run_python("scripts/review_prompt.py", project_root)
        self.complete_latest_review(project_root)
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)
        target.write_text("export const value = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop.returncode, 2)
        self.assertIn("src/app.ts", json.loads(stop.stdout)["message"])

    def test_stop_hook_outputs_strict_json_when_blocking(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop.stderr, "")
        parsed = json.loads(stop.stdout)
        self.assertTrue(parsed["block"])
        self.assertEqual(stop.stdout.strip(), json.dumps(parsed, separators=(",", ":")))

    def test_tracks_multiple_files_from_multiedit_style_payload(self):
        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("export const b = 1;\n", encoding="utf-8")
        payload = {"tool_input": {"edits": [{"file_path": "src/a.ts"}, {"file_path": "src/b.ts"}]}}
        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps(payload))
        self.assertEqual(post.returncode, 0)
        self.assertEqual(sorted(entry["file"] for entry in load_state(project_root)), ["src/a.ts", "src/b.ts"])
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 2)

    def test_includes_real_git_diff_content_in_generated_review_prompt(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=project_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_root, check=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=project_root, check=True)
        subprocess.run(["git", "add", "src/app.ts"], cwd=project_root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=project_root, check=True, capture_output=True, text=True)
        target.write_text("export const value = 2;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        review = self.run_python("scripts/review_prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        prompt = next((project_root / ".claude" / "claude-auto-review" / "run").glob("*prompt.md")).read_text(encoding="utf-8")
        self.assertIn("-export const value = 1;", prompt)
        self.assertIn("+export const value = 2;", prompt)

    def test_includes_snapshots_for_untracked_files_when_git_diff_is_empty(self):
        project_root = self.temp_project()
        (project_root / "src" / "new.ts").write_text("export const created = true;\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=project_root, check=True, capture_output=True, text=True)
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/new.ts"}))
        review = self.run_python("scripts/review_prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        prompt = next((project_root / ".claude" / "claude-auto-review" / "run").glob("*prompt.md")).read_text(encoding="utf-8")
        self.assertIn("## Current File Snapshots", prompt)
        self.assertIn("export const created = true;", prompt)

    def test_review_prompt_includes_custom_project_rules(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        rules_path = project_root / ".claude" / "claude-auto-review" / "rules.md"
        rules_path.write_text("# Custom Rules\n\n- Custom auth rule must appear.\n", encoding="utf-8")

        review = self.run_python("scripts/review_prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        prompt = next((project_root / ".claude" / "claude-auto-review" / "run").glob("*prompt.md")).read_text(encoding="utf-8")
        self.assertIn("Custom auth rule must appear.", prompt)

    def test_review_prompt_describes_deleted_tracked_file(self):
        project_root = self.temp_project()
        append_state(
            {
                "type": "edit",
                "file": "src/deleted.ts",
                "hash": "deadbeef",
                "timestamp": "2026-05-05T01:00:00Z",
                "reviewed": False,
            },
            project_root,
        )

        review = self.run_python("scripts/review_prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        prompt = next((project_root / ".claude" / "claude-auto-review" / "run").glob("*prompt.md")).read_text(encoding="utf-8")
        self.assertIn("## src/deleted.ts", prompt)
        self.assertIn("File does not currently exist.", prompt)

    def test_setup_script_creates_runtime_shims_agents_rules_and_gitignore_entries(self):
        project_root = self.temp_project()
        setup = self.run_python("scripts/setup_claude_auto_review.py", project_root)
        self.assertEqual(setup.returncode, 0)
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py").exists())
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "scripts" / "cancel_claude_auto_review.py").exists())
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "agents" / "reviewer.md").exists())
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "rules.md").exists())
        self.assertIn(".claude/claude-auto-review/state.jsonl", (project_root / ".gitignore").read_text(encoding="utf-8"))
        settings = json.loads((project_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)

    def test_setup_script_is_idempotent_for_gitignore_entries(self):
        project_root = self.temp_project()
        self.run_python("scripts/setup_claude_auto_review.py", project_root)
        self.run_python("scripts/setup_claude_auto_review.py", project_root)
        lines = (project_root / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines.count(".claude/claude-auto-review/state.jsonl"), 1)
        self.assertEqual(lines.count(".claude/claude-auto-review/run/"), 1)
        self.assertEqual(lines.count(".claude/claude-auto-review/reviews/"), 1)
        self.assertEqual(lines.count(".claude/claude-auto-review/scripts/"), 1)
        self.assertEqual(lines.count(".claude/claude-auto-review/agents/"), 1)
        self.assertEqual(lines.count(".claude/claude-auto-review/claude-auto-review.log"), 1)

    def test_project_local_shim_runs_review_prompt(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("scripts/setup_claude_auto_review.py", project_root)
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        shim = project_root / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py"
        result = subprocess.run(
            [sys.executable, str(shim)],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_root)},
        )
        self.assertEqual(result.returncode, 0)
        self.complete_latest_review(project_root)
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

    def test_cancel_script_clears_state_run_and_review_artifacts(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.run_python("scripts/review_prompt.py", project_root)

        cancel = self.run_python("scripts/cancel_claude_auto_review.py", project_root)
        self.assertEqual(cancel.returncode, 0)
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "state.jsonl").exists())
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "run").exists())
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "reviews").exists())
        log_content = (project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log").read_text(encoding="utf-8")
        self.assertIn('"event":"cancel_completed"', log_content)

    def test_project_local_cancel_shim_runs(self):
        project_root = self.temp_project()
        self.run_python("scripts/setup_claude_auto_review.py", project_root)
        append_state(
            {
                "type": "edit",
                "file": "src/app.ts",
                "hash": "deadbeef",
                "timestamp": "2026-05-05T01:00:00Z",
                "reviewed": False,
            },
            project_root,
        )
        shim = project_root / ".claude" / "claude-auto-review" / "scripts" / "cancel_claude_auto_review.py"
        result = subprocess.run(
            [sys.executable, str(shim)],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_root)},
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "state.jsonl").exists())

    def test_hook_configs_match_delete_and_remove_tools(self):
        plugin_config = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        hooks_config = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))

        plugin_matcher = plugin_config["hooks"]["PostToolUse"][0]["matcher"]
        hooks_matcher = hooks_config["hooks"]["PostToolUse"][0]["matcher"]
        for tool_name in ("Write", "Edit", "MultiEdit", "Delete", "Remove"):
            self.assertIn(tool_name, plugin_matcher)
            self.assertIn(tool_name, hooks_matcher)


if __name__ == "__main__":
    unittest.main()
