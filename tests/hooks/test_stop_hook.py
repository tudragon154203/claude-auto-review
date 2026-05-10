import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from scripts.state import append_state, consecutive_stop_blocks, load_state  # noqa: E402
from tests.hooks.support import HookTestCase  # noqa: E402


class TestStopHook(HookTestCase, unittest.TestCase):
    def test_stop_hook_prefers_higher_overlap_over_newer_review(self):
        from datetime import datetime, timedelta, timezone

        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("export const b = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/a.ts"}))
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))

        edits = [e for e in load_state(project_root, "test-session") if e.get("type") == "edit"]
        hash_a = [e["hash"] for e in edits if e.get("file") == "src/a.ts"][-1]
        hash_b = [e["hash"] for e in edits if e.get("file") == "src/b.ts"][-1]

        review_dir = project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        path_high = review_dir / "review-high.md"
        path_new = review_dir / "review-newer.md"
        path_high.write_text("## Verdict\n\nPending.\n", encoding="utf-8")
        path_new.write_text("## Verdict\n\nPending.\n", encoding="utf-8")

        base = datetime.now(timezone.utc)
        ts_old = base.isoformat().replace("+00:00", "Z")
        ts_new = (base + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")

        # Older review covers both files (overlap=2)
        append_state(
            {
                "type": "review",
                "reviewId": "high-overlap",
                "reviewPath": str(path_high),
                "timestamp": ts_old,
                "status": "pending",
                "files": [
                    {"file": "src/a.ts", "hash": hash_a},
                    {"file": "src/b.ts", "hash": hash_b},
                ],
            },
            project_root,
            client_id="test-session",
        )
        # Newer review covers one file only (overlap=1)
        append_state(
            {
                "type": "review",
                "reviewId": "newer-low-overlap",
                "reviewPath": str(path_new),
                "timestamp": ts_new,
                "status": "pending",
                "files": [{"file": "src/a.ts", "hash": hash_a}],
            },
            project_root,
            client_id="test-session",
        )

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop.returncode, 2)
        self.assertIn("Review high-overlap", json.loads(stop.stdout)["message"])

    def test_stop_hook_prefers_newest_pending_review_on_equal_overlap(self):
        from datetime import datetime, timedelta, timezone

        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        current_hash = load_state(project_root, "test-session")[-1]["hash"]
        review_dir = project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        old_path = review_dir / "review-old.md"
        new_path = review_dir / "review-new.md"
        old_path.write_text("## Verdict\n\nPending.\n", encoding="utf-8")
        new_path.write_text("## Verdict\n\nPending.\n", encoding="utf-8")

        base = datetime.now(timezone.utc)
        ts_old = base.isoformat().replace("+00:00", "Z")
        ts_new = (base + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        append_state(
            {
                "type": "review",
                "reviewId": "old",
                "reviewPath": str(old_path),
                "timestamp": ts_old,
                "status": "pending",
                "files": [{"file": "src/app.ts", "hash": current_hash}],
            },
            project_root,
            client_id="test-session",
        )
        append_state(
            {
                "type": "review",
                "reviewId": "new",
                "reviewPath": str(new_path),
                "timestamp": ts_new,
                "status": "pending",
                "files": [{"file": "src/app.ts", "hash": current_hash}],
            },
            project_root,
            client_id="test-session",
        )

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop.returncode, 2)
        self.assertIn("Review new", json.loads(stop.stdout)["message"])

    def test_stop_hook_does_not_clean_expired_reviews_for_payload_session_id(self):
        from datetime import datetime, timedelta, timezone

        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        # Track edit under payload session id; env session id is intentionally different.
        payload = json.dumps({"session_id": "payload-session", "file_path": "src/app.ts"})
        self.run_python("hooks/post_tool_use.py", project_root, payload, client_id="env-session")

        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        append_state(
            {
                "type": "review",
                "reviewId": "expired-payload",
                "reviewPath": str(
                    project_root
                    / ".claude"
                    / "claude-auto-review"
                    / "clients"
                    / "client-payload-session"
                    / "reviews"
                    / "review-expired.md"
                ),
                "timestamp": old_time,
                "status": "pending",
                "files": [{"file": "src/app.ts", "hash": "testhash"}],
            },
            project_root,
            client_id="payload-session",
        )

        stop = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            payload,
            client_id="env-session",
            env_overrides={"PATH": ""},
            use_fake_claude=False,
        )
        self.assertIn(stop.returncode, [0, 2], "Stop should not crash")

        state_after = load_state(project_root, client_id="payload-session")
        pending_ids = [e.get("reviewId") for e in state_after if e.get("type") == "review" and e.get("status") == "pending"]
        self.assertIn("expired-payload", pending_ids)

    def test_review_prompt_creates_prompt_and_allows_later_stop(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        # Stop hook runs review_prompt.py, claude CLI (fake) completes the review
        stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop.returncode, 0)
        self.assertEqual(stop.stdout.strip(), "")

        # Review artifacts should exist (prompt file + possible claude capture)
        run_files = list((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "run").iterdir())
        self.assertGreaterEqual(len(run_files), 1)
        self.assertEqual(
            len(list((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews").iterdir())),
            1,
        )

        # Review file contains the fake claude's verdict
        review_path = sorted(
            (project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews").glob("review-*.md")
        )[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertIn("Clean - no issues found. Claude may stop.", content)

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
        self.assertEqual(stop.returncode, 0)
        self.assertEqual(stop.stdout.strip(), "")
        self.assertTrue(load_state(project_root, "test-session")[-1]["reviewed"])

    def test_stop_hook_outputs_strict_json_when_blocking(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertNotEqual(stop.stderr, "")
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
        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2, "First stop should be blocked")
        state = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state), 1)

        # Step 2: Track a second unreviewed edit -> second block (count = 2)
        (project_root / "src" / "b.ts").write_text("export const b = 2;\n", encoding="utf-8")
        post2 = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))
        self.assertEqual(post2.returncode, 0)
        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2, "Second stop should still be blocked")
        state = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state), 2)

        # Step 3: Track a third unreviewed edit -> third block (count = 3)
        (project_root / "src" / "c.ts").write_text("export const c = 3;\n", encoding="utf-8")
        post3 = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/c.ts"}))
        self.assertEqual(post3.returncode, 0)
        stop3 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop3.returncode, 2, "Third stop should still be blocked (threshold not yet exceeded)")
        state = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state), 3)

        # Step 4: Track a fourth unreviewed edit -> fourth stop should trip the breaker
        (project_root / "src" / "d.ts").write_text("export const d = 4;\n", encoding="utf-8")
        post4 = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/d.ts"}))
        self.assertEqual(post4.returncode, 0)
        stop4 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop4.returncode, 0, "Fourth stop should be ALLOWED: circuit breaker tripped")
        self.assertEqual(stop4.stdout.strip(), "", "Circuit breaker approval prints no block JSON response")
        state_after = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state_after), 3)

    def test_stop_hook_continues_blocking_after_successful_review_then_new_edits(self):
        """After a successful review clears unreviewed files, the stop-block counter is reset."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        # First edit -> auto-review and approve
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

        # New edit after clean state -> auto-review and approve again
        (project_root / "src" / "b.ts").write_text("export const b = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))
        stop = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop.returncode, 0, "New unreviewed edit after clean review should approve again")
        state = load_state(project_root, "test-session")
        self.assertTrue(state[-1]["reviewed"])

    def test_stop_hook_circuit_breaker_settings_override(self):
        """maxStopPasses can be overridden in project settings."""
        project_root = self.temp_project()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"maxStopPasses": 2}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        # First edit -> block (no claude CLI on PATH)
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(
            self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False).returncode, 2)

        # Second edit -> block (count = 2)
        (project_root / "src" / "b.ts").write_text("export const b = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))
        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2, "With maxStopPasses=2, second block should still trigger")

        # Third edit -> should trip: count 3 >= 2
        (project_root / "src" / "c.ts").write_text("export const c = 3;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/c.ts"}))
        stop3 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(
            stop3.returncode, 0, "Circuit breaker with maxStopPasses=2 should trip on third consecutive block"
        )


    def test_stop_hook_creates_subagent_and_waits_for_review(self):
        """Stop hook runs review_prompt.py itself before blocking, then waits for review completion."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        # Step 1: stop hook blocks but has already run review_prompt.py (no claude CLI available)
        stop1 = self.run_python(
            "hooks/stop_hook.py", project_root,
            env_overrides={"PATH": ""},
            use_fake_claude=False,
        )
        self.assertEqual(stop1.returncode, 2)
        parsed = json.loads(stop1.stdout)
        self.assertTrue(parsed["block"])

        # Step 2: verify the stop hook already created the review artifacts
        client_dir = project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session"
        reviews = list((client_dir / "reviews").glob("review-*.md"))
        self.assertEqual(len(reviews), 1, "Stop hook should have already created a review")
        prompts = list((client_dir / "run").glob("*-prompt.md"))
        self.assertEqual(len(prompts), 1, "Stop hook should have already created a prompt")

        # Step 3: stop hook blocks because review is still pending
        stop2 = self.run_python(
            "hooks/stop_hook.py", project_root,
            env_overrides={"PATH": ""},
            use_fake_claude=False,
        )
        self.assertEqual(stop2.returncode, 2)
        # Message indicates review exists but needs completion
        self.assertIn("Review", json.loads(stop2.stdout)["message"])

        # Step 4: complete the review
        self.complete_latest_review(project_root)

        # Step 5: stop hook now allows stopping
        stop3 = self.run_python("hooks/stop_hook.py", project_root)
        self.assertEqual(stop3.returncode, 0, "Stop should be allowed after review is completed")

    def test_pending_review_not_expired_is_used(self):
        """A recent pending review is matched and used normally."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        # First stop creates a pending review
        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        # Second stop should find the pending review (not expired)
        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2)
        parsed = json.loads(stop2.stdout)
        self.assertIn("Review", parsed["message"])

    def test_pending_review_expired_is_skipped_but_not_cleaned_by_stop_hook(self):
        """Stop hook skips expired pending reviews, but cleanup is handled by session_end."""
        from datetime import datetime, timedelta, timezone

        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        state_path = project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "state.jsonl"

        # Create a pending review with an old timestamp (> 1 hour ago)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        append_state(
            {
                "type": "review",
                "reviewId": "rev-expired",
                "reviewPath": str(project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews" / "review-expired.md"),
                "timestamp": old_time,
                "status": "pending",
                "files": [{"file": "src/app.ts", "hash": "testhash"}],
            },
            project_root,
            client_id="test-session",
        )

        # Verify the expired review exists in state before cleanup
        state_before = load_state(project_root, client_id="test-session")
        expired_reviews = [e for e in state_before if e.get("type") == "review" and e.get("status") == "pending"]
        self.assertEqual(len(expired_reviews), 1, "Expired review should be in state")

        # Run stop hook - it should skip expired review and proceed without crashing
        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertIn(stop.returncode, [0, 2], "Stop should not crash")

        # Expired entry remains in state; cleanup moved to session_end.
        state_after = load_state(project_root, client_id="test-session")
        expired_ids = [e.get("reviewId") for e in state_after if e.get("type") == "review" and e.get("status") == "pending"]
        self.assertIn("rev-expired", expired_ids,
            "Stop hook should not remove expired reviews")

    def test_pending_review_timeout_custom_setting_skip_only(self):
        """Stop hook honors timeout for matching, without performing cleanup."""
        from datetime import datetime, timedelta, timezone

        project_root = self.temp_project()
        (project_root / ".claude").mkdir(parents=True, exist_ok=True)
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"pendingReviewTimeoutHours": 0.01}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        # Create a pending review with timestamp from 1 minute ago (exceeds 0.01h = 36s timeout)
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        append_state(
            {
                "type": "review",
                "reviewId": "rev-custom-timeout",
                "reviewPath": str(project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews" / "review-custom.md"),
                "timestamp": old_time,
                "status": "pending",
                "files": [{"file": "src/app.ts", "hash": "testhash"}],
            },
            project_root,
            client_id="test-session",
        )

        # Run stop hook - it reads custom timeout from settings and skips expired review
        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertIn(stop.returncode, [0, 2], "Stop should not crash")

        # Verify expired review still exists; cleanup moved to session_end.
        state_after = load_state(project_root, client_id="test-session")
        expired_ids = [e.get("reviewId") for e in state_after if e.get("type") == "review" and e.get("status") == "pending"]
        self.assertIn("rev-custom-timeout", expired_ids,
            "Stop hook should not remove expired reviews")


if __name__ == "__main__":
    unittest.main()
