"""End-to-end tests exercising the complete review lifecycle across scripts.

Runs actual subprocesses against plugin scripts to verify cross-script
integration: setup → edit tracking → stop blocking → review creation →
review completion → allow stop → cancel.
"""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests.support import SubprocessMixin, TempProjectMixin

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from scripts.state import load_state, get_unreviewed_files


class EndToEndTests(TempProjectMixin, SubprocessMixin, unittest.TestCase):
    """Full-system tests running connected scripts as subprocesses."""

    def temp_project(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-e2e-"))
        (project_root / "src").mkdir(parents=True)
        return project_root

    def track(self, project_root, file_path, client_id="test-session"):
        return self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            json.dumps({"tool_input": {"file_path": file_path}}),
            client_id=client_id,
        )

    def stop(self, project_root, client_id="test-session",
             use_fake_claude=None, env_overrides=None):
        return self.run_python(
            "hooks/stop_hook.py", project_root,
            client_id=client_id,
            use_fake_claude=use_fake_claude,
            env_overrides=env_overrides,
        )

    def review(self, project_root, client_id="test-session"):
        return self.run_python("scripts/review_prompt.py", project_root, client_id=client_id)

    def complete_review(self, project_root, verdict="Clean - no issues found.",
                        client_id="test-session"):
        review_dir = (project_root / ".claude" / "claude-auto-review" /
                      "clients" / f"client-{client_id}" / "reviews")
        review_path = sorted(review_dir.glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        content = content.replace(
            "Pending. Claude must complete this review from",
            "Completed review from",
        )
        content = content.replace("Pending.", verdict)
        review_path.write_text(content, encoding="utf-8", newline="\n")
        return review_path

    def test_full_lifecycle_setup_to_cancel(self):
        project_root = self.temp_project()
        (project_root / "src" / "main.ts").write_text("const x = 1;\n",
                                                      encoding="utf-8")

        setup = self.run_python("scripts/setup_claude_auto_review.py", project_root)
        self.assertEqual(setup.returncode, 0)

        self.track(project_root, "src/main.ts")
        stop1 = self.stop(project_root)
        self.assertEqual(stop1.returncode, 0)
        self.assertEqual(stop1.stdout.strip(), "")

    def test_multiple_sequential_review_cycles(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        no_cli = {"use_fake_claude": False, "env_overrides": {"PATH": ""}}

        target.write_text("v1\n", encoding="utf-8")
        self.track(project_root, "src/app.ts")
        self.assertEqual(self.stop(project_root, **no_cli).returncode, 2)
        self.review(project_root)
        self.complete_review(project_root)
        self.assertEqual(self.stop(project_root).returncode, 0)

        target.write_text("v2\n", encoding="utf-8")
        self.track(project_root, "src/app.ts")
        self.assertEqual(self.stop(project_root, **no_cli).returncode, 2)
        self.review(project_root)
        self.complete_review(project_root)
        self.assertEqual(self.stop(project_root).returncode, 0)

        state = load_state(project_root, "test-session")
        hashes = {e["hash"] for e in state if e.get("type") == "edit"}
        self.assertEqual(len(hashes), 2)

    def test_concurrent_clients_full_workflow(self):
        project_root = self.temp_project()
        (project_root / "src" / "shared.ts").write_text("shared\n",
                                                        encoding="utf-8")
        no_cli = {"use_fake_claude": False, "env_overrides": {"PATH": ""}}

        self.track(project_root, "src/shared.ts", client_id="client-a")
        self.review(project_root, client_id="client-a")

        self.track(project_root, "src/shared.ts", client_id="client-b")
        self.review(project_root, client_id="client-b")

        self.complete_review(project_root, client_id="client-a")
        self.assertEqual(self.stop(project_root, client_id="client-a", **no_cli).returncode, 0)

        stop_b = self.stop(project_root, client_id="client-b", **no_cli)
        self.assertEqual(stop_b.returncode, 2)

        self.complete_review(project_root, client_id="client-b")
        self.assertEqual(self.stop(project_root, client_id="client-b", **no_cli).returncode, 0)

    def test_cancel_mid_review_then_fresh_start(self):
        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("a\n", encoding="utf-8")
        no_cli = {"use_fake_claude": False, "env_overrides": {"PATH": ""}}

        self.track(project_root, "src/a.ts")
        self.review(project_root)

        cancel = self.run_python("scripts/cancel_claude_auto_review.py", project_root)
        self.assertEqual(cancel.returncode, 0)

        (project_root / "src" / "b.ts").write_text("b\n", encoding="utf-8")
        self.track(project_root, "src/b.ts")
        self.assertEqual(self.stop(project_root, **no_cli).returncode, 2)

        self.review(project_root)
        self.complete_review(project_root)
        self.assertEqual(self.stop(project_root).returncode, 0)

    def test_completed_review_allows_stop_immediately(self):
        """After completing a review, the stop hook must allow stopping."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("content\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")
        self.review(project_root)
        self.complete_review(project_root)

        stop_result = self.stop(project_root)
        self.assertEqual(stop_result.returncode, 0,
                         f"Stop should be allowed after completed review, got: {stop_result.stdout}")

    def test_clean_project_stop_allowed_immediately(self):
        project_root = self.temp_project()
        self.assertEqual(self.stop(project_root).returncode, 0)

    def test_multiple_files_single_review_covers_all(self):
        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("a\n", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("b\n", encoding="utf-8")

        self.track(project_root, "src/a.ts")
        self.track(project_root, "src/b.ts")
        self.review(project_root)
        self.complete_review(project_root)
        self.assertEqual(self.stop(project_root).returncode, 0)

        state = load_state(project_root, "test-session")
        unreviewed = get_unreviewed_files(state)
        self.assertEqual(len(unreviewed), 0)

    def test_distinct_review_ids_per_invocation(self):
        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("a\n", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("b\n", encoding="utf-8")

        self.track(project_root, "src/a.ts")
        self.review(project_root)
        self.complete_review(project_root)

        time.sleep(1.1)  # Ensure timestamp-based review ID differs

        (project_root / "src" / "b.ts").write_text("b2\n", encoding="utf-8")
        self.track(project_root, "src/b.ts")
        self.review(project_root)

        state = load_state(project_root, "test-session")
        review_ids = {e["reviewId"] for e in state if e.get("type") == "review"}
        self.assertEqual(len(review_ids), 2)

    def test_stop_block_feedback_contains_actionable_info(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("new file\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")
        stop = self.stop(project_root, use_fake_claude=False, env_overrides={"PATH": ""})

        parsed = json.loads(stop.stdout)
        self.assertIn("Review file created at:", parsed["feedback"])
        self.assertIn("src/app.ts", parsed["message"])

    def test_setup_idempotent_e2e(self):
        project_root = self.temp_project()

        self.assertEqual(
            self.run_python("scripts/setup_claude_auto_review.py",
                            project_root).returncode, 0)
        self.assertEqual(
            self.run_python("scripts/setup_claude_auto_review.py",
                            project_root).returncode, 0)

        self.assertTrue((project_root / ".claude" / "claude-auto-review" /
                         "scripts" / "review_prompt.py").exists())
        self.assertTrue((project_root / ".claude" / "claude-auto-review" /
                         "rules.md").exists())
        settings = json.loads(
            (project_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)

    def test_stop_hook_auto_completes_review_with_fake_claude(self):
        """Stop hook spawns claude CLI, fake CLI writes completed review, stop is approved."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.track(project_root, "src/app.ts")

        # Stop hook runs review_prompt.py internally, then runs fake claude CLI
        stop = self.stop(project_root)
        self.assertEqual(stop.returncode, 0)
        self.assertEqual(stop.stdout.strip(), "")

        # Verify review was created by stop_hook calling review_prompt.py
        client_dir = (project_root / ".claude" / "claude-auto-review" /
                      "clients" / "client-test-session")
        review_path = sorted((client_dir / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        # Fake claude output should be written to review file
        self.assertIn("Clean - no issues found. Claude may stop.", content)

        # Verify the prompt file was created for the subagent
        prompts = list((client_dir / "run").glob("review-*-prompt.md"))
        self.assertEqual(len(prompts), 1)

        # Verify claude CLI was invoked with correct args
        capture = client_dir / "run" / "claude-cli-args.json"
        self.assertTrue(capture.exists(), "Fake claude should have captured its argv")
        cli_args = json.loads(capture.read_text(encoding="utf-8"))
        self.assertIn("--print", cli_args)
        self.assertIn("--model", cli_args)
        idx = cli_args.index("--model")
        self.assertEqual(cli_args[idx + 1], "fast")
        self.assertIn("--permission-mode", cli_args)
        idx = cli_args.index("--permission-mode")
        self.assertEqual(cli_args[idx + 1], "acceptEdits")
        self.assertIn("--system-prompt-file", cli_args)

        # Verify files are marked reviewed
        state = load_state(project_root, "test-session")
        self.assertTrue(state[-1].get("reviewed", False))

        # No unreviewed files remain
        self.assertEqual(len(get_unreviewed_files(state)), 0)


if __name__ == "__main__":
    unittest.main()
