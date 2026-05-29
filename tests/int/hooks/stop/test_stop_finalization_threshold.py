import json
import unittest

from claude_auto_review.state.store.read import load_state
from tests.int.hooks.support import HookTestCase
from tests.support import start_classifier_server


class TestStopFinalizationThreshold(HookTestCase, unittest.TestCase):
    def test_stop_allows_findings_below_configured_threshold(self):
        project_root = self.temp_project()
        settings_dir = project_root / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"minimumBlockingSeverity": "high"}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        review_path = self.complete_latest_review(project_root, verdict="Clean - no issues found. Claude may stop.")
        content = review_path.read_text(encoding="utf-8")
        review_path.write_text(
            content.replace(
                "No findings yet. This file is a placeholder until Claude completes the review.",
                "### 1. [Medium] Advisory issue\n**Verdict:** Confirmed\n",
            ),
            encoding="utf-8",
            newline="\n",
        )

        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 0)

    def test_stop_allowed_when_classifier_overrides_blocking(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        server, base_url = start_classifier_server("incomplete")
        try:
            payload = json.dumps({"last_assistant_message": "I will finish this later."})
            result = self.run_python(
                "hooks/stop_hook.py",
                project_root,
                input_text=payload,
                env_overrides={
                    "ANTHROPIC_BASE_URL": base_url,
                    "ANTHROPIC_API_KEY": "secret-key",
                    "PATH": "",
                },
                use_fake_claude=False,
            )
            self.assertEqual(result.returncode, 0)
        finally:
            server.shutdown()
            server.server_close()

    def test_partial_review_allowed_when_classifier_overrides_blocking(self):
        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("a", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("b", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/a.ts"}))

        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))

        self.complete_latest_review(project_root, verdict="Clean - no issues found. Claude may stop.")

        server, base_url = start_classifier_server("incomplete")
        try:
            payload = json.dumps({"last_assistant_message": "Stopping now, b.ts will be reviewed later."})
            result = self.run_python(
                "hooks/stop_hook.py",
                project_root,
                input_text=payload,
                env_overrides={
                    "ANTHROPIC_BASE_URL": base_url,
                    "ANTHROPIC_API_KEY": "secret-key",
                    "PATH": "",
                },
                use_fake_claude=False,
            )
            self.assertEqual(result.returncode, 0)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
