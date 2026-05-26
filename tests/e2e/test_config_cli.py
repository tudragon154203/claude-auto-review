import json
import subprocess
import sys
from pathlib import Path

from tests.e2e.support import EndToEndTestCase


class EndToEndConfigCliTests(EndToEndTestCase):
    def test_config_non_interactive_initializes_project(self):
        project_root = self.temp_project()

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "claude_auto_review.cli",
                "config",
                "--backend",
                "codex",
                "--severity",
                "high",
                "--max-stop-passes",
                "7",
                "--non-interactive",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**subprocess.os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py").exists())
        self.assertTrue((project_root / ".claude" / "claude-auto-review" / "agents" / "reviewer.md").exists())
        settings = json.loads((project_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["claude-auto-review"]["reviewerBackend"], "codex")
        self.assertEqual(settings["claude-auto-review"]["reviewerModel"], "gpt-5.3-codex")
        self.assertEqual(settings["claude-auto-review"]["minimumBlockingSeverity"], "high")
        self.assertEqual(settings["claude-auto-review"]["maxStopPasses"], 7)
        self.assertIn("Full config location", result.stdout)

    def test_config_interactive_accepts_stdin_answers(self):
        project_root = self.temp_project()

        result = subprocess.run(
            [sys.executable, "-m", "claude_auto_review.cli", "config"],
            cwd=project_root,
            input="codex\ngpt-5.3-codex\nhigh\n8\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**subprocess.os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads((project_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["claude-auto-review"]["reviewerBackend"], "codex")
        self.assertEqual(settings["claude-auto-review"]["reviewerModel"], "gpt-5.3-codex")
        self.assertEqual(settings["claude-auto-review"]["minimumBlockingSeverity"], "high")
        self.assertEqual(settings["claude-auto-review"]["maxStopPasses"], 8)
        self.assertIn("Claude Auto Review setup wizard", result.stdout)

    def test_config_then_review_flow_still_works(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("const value = 1;\n", encoding="utf-8")

        config = subprocess.run(
            [
                sys.executable,
                "-m",
                "claude_auto_review.cli",
                "config",
                "--backend",
                "codex",
                "--max-stop-passes",
                "7",
                "--non-interactive",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**subprocess.os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        )
        self.assertEqual(config.returncode, 0, config.stderr)

        self.track(project_root, "src/app.ts")
        review = self.review(project_root)
        self.assertEqual(review.returncode, 0, review.stderr)

        stop_blocked = self.stop(project_root, use_fake_claude=False, env_overrides={"PATH": ""})
        self.assertEqual(stop_blocked.returncode, 2)

        self.complete_review(project_root)
        stop_allowed = self.stop(project_root, use_fake_claude=False, env_overrides={"PATH": ""})
        self.assertEqual(stop_allowed.returncode, 0)
