import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from claude_auto_review.state.store.read import load_state  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402
from tests.support import client_dir  # noqa: E402


class TestStopHookLifecycle(HookTestCase, unittest.TestCase):
    def test_review_prompt_creates_prompt_and_allows_later_stop(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop.returncode, 0)
        approve = json.loads(stop.stdout.strip())
        self.assertNotIn("decision", approve)
        self.assertIn("Claude Auto Review", approve["systemMessage"])

        _cd = client_dir(project_root)
        run_files = list((_cd / "run").iterdir())
        self.assertGreaterEqual(len(run_files), 1)
        self.assertEqual(
            len(list((_cd / "reviews").iterdir())),
            1,
        )

        review_path = sorted(
            (_cd / "reviews").glob("review-*.md")
        )[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertIn("Clean - no issues found. Claude may stop.", content)

    def test_treats_previously_reviewed_identical_hash_as_already_reviewed(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.run_python("claude_auto_review/review/prompt.py", project_root)
        self.complete_latest_review(project_root)
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)
        post_again = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(post_again.returncode, 0)
        self.assertTrue(load_state(project_root, "test-session")[-1].reviewed)
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

    def test_reblocks_after_reviewed_file_changes_to_new_hash(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.run_python("claude_auto_review/review/prompt.py", project_root)
        self.complete_latest_review(project_root)
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)
        target.write_text("export const value = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop.returncode, 0)
        approve = json.loads(stop.stdout.strip())
        self.assertNotIn("decision", approve)
        self.assertIn("Claude Auto Review", approve["systemMessage"])
        self.assertTrue(load_state(project_root, "test-session")[-1].reviewed)

    def test_stop_hook_outputs_strict_json_when_blocking(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertNotEqual(stop.stderr, "")
        parsed = json.loads(stop.stdout)
        self.assertEqual(parsed["decision"], "block")
        self.assertIn("reason", parsed)
        self.assertIn("systemMessage", parsed)
        self.assertNotIn("block", parsed)
        self.assertNotIn("message", parsed)
        self.assertNotIn("feedback", parsed)
        self.assertEqual(stop.stdout.strip(), json.dumps(parsed, separators=(",", ":")))

    def test_stop_hook_continues_blocking_after_successful_review_then_new_edits(self):
        """After a successful review clears unreviewed files, the stop-block counter is reset."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

        (project_root / "src" / "b.ts").write_text("export const b = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))
        stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop.returncode, 0, "New unreviewed edit after clean review should approve again")
        state = load_state(project_root, "test-session")
        self.assertTrue(state[-1].reviewed)

    def test_stop_hook_creates_subagent_and_waits_for_review(self):
        """Stop hook runs review_prompt.py itself before blocking, then waits for review completion."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop1 = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            env_overrides={"PATH": ""},
            use_fake_claude=False,
        )
        self.assertEqual(stop1.returncode, 2)
        parsed = json.loads(stop1.stdout)
        self.assertEqual(parsed["decision"], "block")

        _cd = client_dir(project_root)
        reviews = list((_cd / "reviews").glob("review-*.md"))
        self.assertEqual(len(reviews), 1, "Stop hook should have already created a review")
        prompts = list((_cd / "run").glob("*-prompt.md"))
        self.assertEqual(len(prompts), 1, "Stop hook should have already created a prompt")

        stop2 = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            env_overrides={"PATH": ""},
            use_fake_claude=False,
        )
        self.assertEqual(stop2.returncode, 2)
        self.assertIn("Review", json.loads(stop2.stdout)["systemMessage"])

        self.complete_latest_review(project_root)

        stop3 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop3.returncode, 0, "Stop should be allowed after review is completed")
