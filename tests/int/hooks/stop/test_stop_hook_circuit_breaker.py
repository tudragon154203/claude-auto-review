import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from claude_auto_review.state.store.read import consecutive_stop_blocks, load_state  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402


class TestStopHookCircuitBreaker(HookTestCase, unittest.TestCase):
    def test_stop_hook_circuit_breaker_opens_after_max_consecutive_blocks(self):
        """When maxStopPasses (default 3) consecutive block events accumulate, the hook allows stop."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        for name in ["app", "b", "c"]:
            (project_root / "src" / f"{name}.ts").write_text(f"export const {name} = 1;\n", encoding="utf-8")
            post = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": f"src/{name}.ts"}))
            self.assertEqual(post.returncode, 0)
            stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
            self.assertEqual(stop.returncode, 2)

        state = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state), 3)

        (project_root / "src" / "d.ts").write_text("export const d = 4;\n", encoding="utf-8")
        post4 = self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/d.ts"}))
        self.assertEqual(post4.returncode, 0)
        stop4 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop4.returncode, 0, "Fourth stop should be ALLOWED: circuit breaker tripped")
        self.assertEqual(stop4.stdout.strip(), "", "Circuit breaker approval prints no block JSON response")
        state_after = load_state(project_root, "test-session")
        self.assertEqual(consecutive_stop_blocks(state_after), 3)

    def test_stop_hook_circuit_breaker_settings_override(self):
        """maxStopPasses can be overridden in project settings."""
        project_root = self.temp_project()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"maxStopPasses": 2}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.assertEqual(
            self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False).returncode,
            2,
        )

        (project_root / "src" / "b.ts").write_text("export const b = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))
        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2, "With maxStopPasses=2, second block should still trigger")

        (project_root / "src" / "c.ts").write_text("export const c = 3;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/c.ts"}))
        stop3 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(
            stop3.returncode,
            0,
            "Circuit breaker with maxStopPasses=2 should trip on third consecutive block",
        )

    def test_stop_hook_invalid_numeric_settings_fall_back_instead_of_failing_open(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir()
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"maxStopPasses": "bad", "pendingReviewTimeoutHours": "bad"}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)

        self.assertEqual(stop.returncode, 2, "Malformed numeric settings should not allow stop with unreviewed changes")
