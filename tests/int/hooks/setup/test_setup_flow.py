import json
import subprocess
import sys
import unittest
from pathlib import Path

from tests.int.hooks.support import HookTestCase


class TestSetupFlow(HookTestCase, unittest.TestCase):
    def test_setup_script_creates_runtime_shims_agents_rules_and_gitignore_entries(self):
        project_root = self.temp_project()
        setup = self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.assertEqual(setup.returncode, 0)
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py").exists())
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "scripts" / "cancel_claude_auto_review.py").exists())
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "agents" / "reviewer.md").exists())
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "review-rules.md").exists())
        self.assertNotIn(".claude/claude-auto-review/state.jsonl", (project_root / ".gitignore").read_text(encoding="utf-8"))
        self.assertIn(".claude/claude-auto-review/", (project_root / ".gitignore").read_text(encoding="utf-8"))
        settings = json.loads((project_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("claude-auto-review", settings)
        self.assertIn("hooks", settings)
        self.assertIn("PostToolUse", settings["hooks"])
        self.assertIn("Stop", settings["hooks"])
        self.assertIn("SessionEnd", settings["hooks"])

    def test_setup_script_preserves_existing_hooks_when_installing(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python custom-stop.py",
                                    }
                                ]
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        setup = self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.assertEqual(setup.returncode, 0)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        stop_commands = [
            hook["command"]
            for entry in settings["hooks"]["Stop"]
            for hook in entry["hooks"]
        ]
        self.assertIn("python custom-stop.py", stop_commands)
        self.assertIn("python -m claude_auto_review.hooks.stop_hook", stop_commands)

    def test_setup_script_is_idempotent_for_gitignore_entries(self):
        project_root = self.temp_project()
        self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        lines = (project_root / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines.count(".claude/claude-auto-review/"), 1)
        self.assertEqual(lines.count(".claude/claude-auto-review/state.jsonl"), 0)
        self.assertEqual(lines.count(".claude/claude-auto-review/clients/*/run/"), 0)
        self.assertEqual(lines.count(".claude/claude-auto-review/clients/*/reviews/"), 0)
        self.assertEqual(lines.count(".claude/claude-auto-review/scripts/"), 0)
        self.assertEqual(lines.count(".claude/claude-auto-review/agents/"), 0)

    def test_setup_script_is_idempotent_for_hooks_entries(self):
        project_root = self.temp_project()
        self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        settings = json.loads((project_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(len(settings["hooks"]["PostToolUse"]), 1)
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(len(settings["hooks"]["SessionEnd"]), 1)

    def test_project_local_shim_runs_review_prompt(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        shim = project_root / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py"
        result = subprocess.run(
            [sys.executable, str(shim)],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**subprocess.os.environ, "CLAUDE_PROJECT_DIR": str(project_root), "CLAUDE_SESSION_ID": "test-session"},
        )
        self.assertEqual(result.returncode, 0)
        self.complete_latest_review(project_root)
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)


if __name__ == "__main__":
    unittest.main()
