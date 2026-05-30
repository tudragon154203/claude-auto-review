import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from claude_auto_review.state.models import EditRecord  # noqa: E402
from claude_auto_review.state.store.queries import consecutive_stop_blocks  # noqa: E402
from claude_auto_review.state.store.read import load_state  # noqa: E402
from claude_auto_review.state.store.write import append_state_event  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402


class TestStopHookCircuitBreaker(HookTestCase, unittest.TestCase):
    CLIENT_ID = "test-session"

    def setUp(self):
        super().setUp()
        self.project_root = self.temp_project()
        state_file = self.project_root / ".claude" / "claude-auto-review" / "clients" / self.CLIENT_ID / "state.jsonl"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        if state_file.exists():
            state_file.unlink()

    def test_stop_hook_circuit_breaker_opens_after_max_consecutive_blocks(self):
        """When maxStopPasses (default 5) consecutive block events accumulate, the hook allows stop."""
        project_root = self.project_root
        client_id = self.CLIENT_ID
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"lastAssistantMessageClassifierEnabled": False}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(post.returncode, 0)

        for _ in range(5):
            stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
            self.assertEqual(stop.returncode, 2)

        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 5)

        stop6 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop6.returncode, 0, "Sixth stop should be ALLOWED: circuit breaker tripped")
        approve = json.loads(stop6.stdout.strip())
        self.assertNotIn("decision", approve, "allow-path should not include decision field")
        self.assertIn("Claude Auto Review", approve["systemMessage"])
        self.assertEqual(approve["systemMessage"], "Claude Auto Review: stop approved (circuit_breaker)")
        state_after = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state_after), 5)

        append_state_event(
            EditRecord(
                timestamp="2026-05-19T16:55:00+07:00",
                file="src/app.ts",
                hash="2",
                reviewed=True,
                reviewId="rev-reset",
            ),
            project_root,
            client_id=client_id,
        )
        stop_reset = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        reset_decision = json.loads(stop_reset.stdout.strip())
        self.assertEqual(stop_reset.returncode, 0)
        self.assertNotIn("decision", reset_decision)
        self.assertEqual(reset_decision["systemMessage"], "Claude Auto Review: stop approved (no_unreviewed_files)")
        state_reset = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state_reset), 0)

    def test_stop_hook_circuit_breaker_settings_override(self):
        """maxStopPasses can be overridden in project settings."""
        project_root = self.project_root
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"maxStopPasses": 2, "lastAssistantMessageClassifierEnabled": False}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2, "With maxStopPasses=2, second block should still trigger")

        stop3 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(
            stop3.returncode,
            0,
            "Circuit breaker with maxStopPasses=2 should trip on third consecutive block",
        )

    def test_stop_hook_invalid_numeric_settings_fall_back_instead_of_failing_open(self):
        project_root = self.project_root
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"maxStopPasses": "bad", "pendingReviewTimeoutHours": "bad"}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)

        self.assertEqual(stop.returncode, 2, "Malformed numeric settings should not allow stop with unreviewed changes")
