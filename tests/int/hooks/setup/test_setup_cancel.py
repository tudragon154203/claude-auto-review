import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.paths.path_utils import get_state_path  # noqa: E402
from claude_auto_review.state.models import EditRecord  # noqa: E402
from claude_auto_review.state.store.write import append_state_event  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402


class TestSetupCancel(HookTestCase, unittest.TestCase):
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
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_root), "CLAUDE_SESSION_ID": "test-session"},
        )
        self.assertEqual(result.returncode, 0)
        self.complete_latest_review(project_root)
        self.assertEqual(self.run_python("hooks/stop_hook.py", project_root).returncode, 0)

    def test_cancel_script_clears_state_run_and_review_artifacts(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        self.run_python("claude_auto_review/review/prompt.py", project_root)

        cancel = self.run_python("claude_auto_review/install/cancel_cli.py", project_root)
        self.assertEqual(cancel.returncode, 0)
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "state.jsonl").exists())
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "run").exists())
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews").exists())
        log_content = get_state_path(project_root).read_text(encoding="utf-8")
        self.assertIn('"type":"cancel_completed"', log_content)

    def test_uninstall_script_removes_hooks_and_legacy_gitignore_entries(self):
        project_root = self.temp_project()
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(
                {
                    "claude-auto-review": {"maxStopPasses": 3},
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python -m claude_auto_review.hooks.stop_hook",
                                        "timeout": 660,
                                    }
                                ]
                            }
                        ],
                        "PostToolUse": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python -m claude_auto_review.hooks.post_tool_use",
                                    }
                                ]
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        runtime_dir = project_root / ".claude" / "claude-auto-review"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (project_root / ".gitignore").write_text(
            "\n".join(
                [
                    ".claude/claude-auto-review/",
                    ".claude/claude-auto-review/state.jsonl",
                    ".claude/claude-auto-review/clients/*/run/",
                    ".claude/claude-auto-review/clients/*/reviews/",
                    ".claude/claude-auto-review/scripts/",
                    ".claude/claude-auto-review/agents/",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        uninstall = subprocess.run(
            [sys.executable, str(REPO_ROOT / "claude_auto_review" / "install" / "uninstall_cli.py")],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_root)},
        )
        self.assertEqual(uninstall.returncode, 0)
        self.assertFalse(runtime_dir.exists())

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertNotIn("claude-auto-review", settings)
        self.assertNotIn("hooks", settings)

        lines = (project_root / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertNotIn(".claude/claude-auto-review/", lines)
        self.assertNotIn(".claude/claude-auto-review/state.jsonl", lines)
        self.assertNotIn(".claude/claude-auto-review/clients/*/run/", lines)
        self.assertNotIn(".claude/claude-auto-review/clients/*/reviews/", lines)
        self.assertNotIn(".claude/claude-auto-review/scripts/", lines)
        self.assertNotIn(".claude/claude-auto-review/agents/", lines)

    def test_project_local_cancel_shim_runs(self):
        project_root = self.temp_project()
        self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        append_state_event(
            EditRecord(
                timestamp="2026-05-05T08:00:00+07:00",
                file="src/app.ts",
                hash="deadbeef",
                reviewed=False,
            ),
            project_root,
            client_id="test-session",
        )
        shim = project_root / ".claude" / "claude-auto-review" / "scripts" / "cancel_claude_auto_review.py"
        result = subprocess.run(
            [sys.executable, str(shim)],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_root), "CLAUDE_SESSION_ID": "test-session"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "state.jsonl").exists())

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

