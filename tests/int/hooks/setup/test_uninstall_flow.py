import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from tests.int.hooks.support import HookTestCase  # noqa: E402


class TestUninstallFlow(HookTestCase, unittest.TestCase):
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
            [sys.executable, str(REPO_ROOT / "claude_auto_review" / "install" / "cli" / "uninstall.py")],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**subprocess.os.environ, "CLAUDE_PROJECT_DIR": str(project_root)},
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


if __name__ == "__main__":
    unittest.main()
