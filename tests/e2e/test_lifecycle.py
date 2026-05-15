import json
import sys
from pathlib import Path

from tests.e2e.support import EndToEndTestCase

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from claude_auto_review.state.store_read import get_unreviewed_files, load_state


class EndToEndLifecycleTests(EndToEndTestCase):
    def test_full_lifecycle_setup_to_cancel(self):
        project_root = self.temp_project()
        (project_root / "src" / "main.ts").write_text("const x = 1;\n", encoding="utf-8")

        setup = self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.assertEqual(setup.returncode, 0)

        self.track(project_root, "src/main.ts")
        stop1 = self.stop(project_root)
        self.assertEqual(stop1.returncode, 0)
        self.assertEqual(stop1.stdout.strip(), "")

    def test_setup_installs_runtime_artifacts_and_review_flow(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("const value = 1;\n", encoding="utf-8")

        setup = self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.assertEqual(setup.returncode, 0, setup.stderr)
        self.assertTrue(self.runtime_script(project_root, "review_prompt.py").exists())
        self.assertTrue(self.runtime_script(project_root, "cancel_claude_auto_review.py").exists())

        self.track(project_root, "src/app.ts")
        review = self.review(project_root)
        self.assertEqual(review.returncode, 0, review.stderr)
        self.assertIn("Review file initialized:", review.stdout)

        stop_blocked = self.stop(project_root, use_fake_claude=False, env_overrides={"PATH": ""})
        self.assertEqual(stop_blocked.returncode, 2)

        self.complete_review(project_root)
        stop_allowed = self.stop(project_root, use_fake_claude=False, env_overrides={"PATH": ""})
        self.assertEqual(stop_allowed.returncode, 0)
        state = load_state(project_root, "test-session")
        self.assertEqual(len(get_unreviewed_files(state)), 0)

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
        hashes = {e.hash for e in state if e.type == "edit"}
        self.assertEqual(len(hashes), 2)

    def test_concurrent_clients_full_workflow(self):
        project_root = self.temp_project()
        (project_root / "src" / "shared.ts").write_text("shared\n", encoding="utf-8")
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

        cancel = self.run_python("claude_auto_review/install/cancel_cli.py", project_root)
        self.assertEqual(cancel.returncode, 0)

        (project_root / "src" / "b.ts").write_text("b\n", encoding="utf-8")
        self.track(project_root, "src/b.ts")
        self.assertEqual(self.stop(project_root, **no_cli).returncode, 2)

        self.review(project_root)
        self.complete_review(project_root)
        self.assertEqual(self.stop(project_root).returncode, 0)

    def test_completed_review_allows_stop_immediately(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("content\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")
        self.review(project_root)
        self.complete_review(project_root)

        stop_result = self.stop(project_root)
        self.assertEqual(stop_result.returncode, 0, f"Stop should be allowed after completed review, got: {stop_result.stdout}")

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

        (project_root / "src" / "b.ts").write_text("b2\n", encoding="utf-8")
        self.track(project_root, "src/b.ts")
        self.review(project_root)

        state = load_state(project_root, "test-session")
        review_ids = {e.reviewId for e in state if e.type == "review"}
        self.assertEqual(len(review_ids), 2)

    def test_stop_block_feedback_contains_actionable_info(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("new file\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")
        stop = self.stop(project_root, use_fake_claude=False, env_overrides={"PATH": ""})

        parsed = json.loads(stop.stdout)
        self.assertEqual(parsed["decision"], "block")
        self.assertIn("Review file created at:", parsed["reason"])
        self.assertIn("This file is only a placeholder until the review is completed.", parsed["reason"])
        self.assertIn("Complete the review from:", parsed["reason"])
        self.assertIn("review-", parsed["reason"])
        self.assertIn("-prompt.md", parsed["reason"])
        rel_segment = ".claude/claude-auto-review/clients"
        self.assertIn(rel_segment, parsed["reason"])
        self.assertNotIn(str(project_root), parsed["reason"])
        self.assertIn("src/app.ts", parsed["systemMessage"])

    def test_setup_idempotent_e2e(self):
        project_root = self.temp_project()

        self.assertEqual(self.run_python("claude_auto_review/install/setup_cli.py", project_root).returncode, 0)
        self.assertEqual(self.run_python("claude_auto_review/install/setup_cli.py", project_root).returncode, 0)

        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py").exists())
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "review-rules.md").exists())
        settings = json.loads((project_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
