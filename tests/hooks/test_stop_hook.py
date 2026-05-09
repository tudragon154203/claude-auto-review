import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from state import consecutive_stop_blocks, load_state  # noqa: E402
from tests.hooks.support import HookTestCase  # noqa: E402


class TestStopHook(HookTestCase, unittest.TestCase):
    def test_review_prompt_creates_prompt_and_allows_later_stop(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        review = self.run_python("scripts/review_prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        self.assertEqual(
            len(list((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "run").iterdir())),
            1,
        )
        self.assertEqual(
            len(list((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews").iterdir())),
            1,
        )
        pending_stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(pending_stop.returncode, 2)
        self.assertIn("still pending", json.loads(pending_stop.stdout)["message"])
        self.complete_latest_review(project_root)
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
        self.assertTrue(load_state(project_root, "test-session")[-1]["reviewed"])
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

    def test_stop_hook_circuit_breaker_opens_after_max_consecutive_blocks(self):
        """When maxStopPasses (default 3) consecutive block events accumulate, the hook allows stop."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        # Step 1: Track an unreviewed edit -> first block (count = 1)
        post1 = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(post1.returncode, 0)
        stop1 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop1.returncode, 2, "First stop should be blocked")
        state = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state), 1)

        # Step 2: Track a second unreviewed edit -> second block (count = 2)
        (project_root / "src" / "b.ts").write_text("export const b = 2;\n", encoding="utf-8")
        post2 = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))
        self.assertEqual(post2.returncode, 0)
        stop2 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop2.returncode, 2, "Second stop should still be blocked")
        state = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state), 2)

        # Step 3: Track a third unreviewed edit -> third block (count = 3)
        (project_root / "src" / "c.ts").write_text("export const c = 3;\n", encoding="utf-8")
        post3 = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/c.ts"}))
        self.assertEqual(post3.returncode, 0)
        stop3 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop3.returncode, 2, "Third stop should still be blocked (threshold not yet exceeded)")
        state = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state), 3)

        # Step 4: Track a fourth unreviewed edit -> fourth stop should trip the breaker
        (project_root / "src" / "d.ts").write_text("export const d = 4;\n", encoding="utf-8")
        post4 = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/d.ts"}))
        self.assertEqual(post4.returncode, 0)
        stop4 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop4.returncode, 0, "Fourth stop should be ALLOWED: circuit breaker tripped")
        self.assertEqual(stop4.stdout.strip(), "", "Circuit breaker approval prints no block JSON response")
        state_after = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state_after), 3)

    def test_stop_hook_continues_blocking_after_successful_review_then_new_edits(self):
        """After a successful review clears unreviewed files, the stop-block counter is reset."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        # First edit -> block
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 2)

        # Start a review
        self.run_python("scripts/review_prompt.py", project_root)

        # Complete the review
        review_path = sorted(
            (project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews").glob("review-*.md")
        )[-1]
        content = review_path.read_text(encoding="utf-8")
        completed = content.replace("Pending.", "Clean - no issues found. Claude may stop.")
        review_path.write_text(completed, encoding="utf-8", newline="\n")

        # Review complete -> stop allowed
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

        # New edit after clean state -> block count resets to fresh state (0 -> 1)
        (project_root / "src" / "b.ts").write_text("export const b = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))
        stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop.returncode, 2, "New unreviewed edit after clean review should block again")
        state = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state), 1)

    def test_stop_hook_circuit_breaker_settings_override(self):
        """maxStopPasses can be overridden in project settings."""
        project_root = self.temp_project()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"maxStopPasses": 2}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        # First edit -> block
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 2)

        # Second edit -> block (count = 2)
        (project_root / "src" / "b.ts").write_text("export const b = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))
        stop2 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop2.returncode, 2, "With maxStopPasses=2, second block should still trigger")

        # Third edit -> should trip: count 3 >= 2
        (project_root / "src" / "c.ts").write_text("export const c = 3;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/c.ts"}))
        stop3 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(
            stop3.returncode, 0, "Circuit breaker with maxStopPasses=2 should trip on third consecutive block"
        )


    def test_stop_hook_creates_subagent_and_waits_for_review(self):
        """Stop hook blocks, spawns review_prompt as a subagent, waits for it, then allows stop."""
        import os
        import subprocess

        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        # Step 1: stop hook blocks with no pending review
        stop1 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop1.returncode, 2)
        parsed = json.loads(stop1.stdout)
        self.assertTrue(parsed["block"])

        # Step 2: extract the command from feedback and spawn a subagent subprocess
        command = None
        for line in parsed["feedback"].splitlines():
            if line.strip().startswith("python"):
                command = line.strip()
                break
        self.assertIsNotNone(command, f"Expected a python command in feedback: {parsed['feedback']}")

        env = {
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(project_root),
            "CLAUDE_SESSION_ID": "test-session",
        }
        subagent = subprocess.Popen(
            command,
            shell=True,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        # Step 3: wait for the subagent to finish creating the review
        stdout, stderr = subagent.communicate(timeout=30)
        self.assertEqual(subagent.returncode, 0, f"Subagent failed: {stderr.decode('utf-8', errors='replace')}")

        # Step 4: verify the subagent created the review artifacts
        client_dir = project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session"
        reviews = list((client_dir / "reviews").glob("review-*.md"))
        self.assertEqual(len(reviews), 1, "Subagent should have created exactly one review")
        prompts = list((client_dir / "run").glob("*-prompt.md"))
        self.assertEqual(len(prompts), 1, "Subagent should have created exactly one prompt")

        # Step 5: stop hook now blocks because review is pending
        stop2 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop2.returncode, 2)
        self.assertIn("still pending", json.loads(stop2.stdout)["message"])

        # Step 6: complete the review (simulating what the subagent reviewer would do)
        self.complete_latest_review(project_root)

        # Step 7: stop hook now allows stopping
        stop3 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop3.returncode, 0, "Stop should be allowed after subagent completes the review")


if __name__ == "__main__":
    unittest.main()
