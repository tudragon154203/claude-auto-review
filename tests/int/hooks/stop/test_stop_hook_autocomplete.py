#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.state.reviews.completion import is_review_complete  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402
from tests.support import client_dir  # noqa: E402


class TestStopHookAutocomplete(HookTestCase, unittest.TestCase):
    def test_stop_hook_with_cli_stub_completes_review(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            input_text=json.dumps({"file_path": "src/app.ts"}),
        )

        stop = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            timeout=660,
        )

        self.assertEqual(
            stop.returncode, 0, f"stop should succeed; stdout={stop.stdout[:200]}; stderr={stop.stderr[:200]}"
        )
        approve = json.loads(stop.stdout.strip())
        self.assertNotIn("decision", approve)
        self.assertIn("Claude Auto Review", approve["systemMessage"])

        review_dir = client_dir(project_root) / "reviews"
        review_path = sorted(review_dir.glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertIn("## Verdict", content)
        self.assertNotIn("Pending.", content)
        self.assertTrue(is_review_complete(review_path))

        log_path = client_dir(project_root) / "state.jsonl"
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn("stop_hook_reviewer_done", log_content)

    def test_stop_hook_with_fake_codex_completes_review(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        settings_dir = project_root / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"reviewerBackend": "codex"}}),
            encoding="utf-8",
        )

        self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            input_text=json.dumps({"file_path": "src/app.ts"}),
        )

        stop = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            use_fake_claude=False,
            use_fake_codex=True,
            timeout=660,
        )

        self.assertEqual(
            stop.returncode, 0, f"stop should succeed; stdout={stop.stdout[:200]}; stderr={stop.stderr[:200]}"
        )
        approve = json.loads(stop.stdout.strip())
        self.assertNotIn("decision", approve)
        self.assertIn("Claude Auto Review", approve["systemMessage"])

        review_dir = client_dir(project_root) / "reviews"
        review_path = sorted(review_dir.glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertIn("## Verdict", content)
        self.assertNotIn("Pending.", content)
        self.assertTrue(is_review_complete(review_path))

        run_dir = client_dir(project_root) / "run"
        cli_args = json.loads((run_dir / "codex-cli-args.json").read_text(encoding="utf-8"))
        self.assertEqual(
            cli_args[:5],
            ["exec", "--skip-git-repo-check", "--sandbox", "read-only", "--model"],
        )
        self.assertEqual(cli_args[5], "gpt-5.3-codex")
        self.assertEqual(cli_args[-1], "-")
        self.assertIn("--output-last-message", cli_args)
        stdin_text = (run_dir / "codex-cli-stdin.txt").read_text(encoding="utf-8")
        self.assertIn("# Claude Auto Review Request", stdin_text)
        self.assertIn("Complete the review", stdin_text)

        log_path = client_dir(project_root) / "state.jsonl"
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn("stop_hook_reviewer_done", log_content)
        self.assertIn('"backend":"codex"', log_content)

    def test_stop_hook_with_empty_codex_output_blocks_pending_review(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        settings_dir = project_root / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"reviewerBackend": "codex"}}),
            encoding="utf-8",
        )

        self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            input_text=json.dumps({"file_path": "src/app.ts"}),
        )

        stop = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            use_fake_claude=False,
            use_fake_codex=True,
            env_overrides={"CODEX_FAKE_MODE": "empty"},
            timeout=660,
        )

        self.assertEqual(
            stop.returncode, 2, f"stop should block; stdout={stop.stdout[:200]}; stderr={stop.stderr[:200]}"
        )
        response = json.loads(stop.stdout.strip())
        self.assertEqual(response["decision"], "block")
        self.assertIn("Claude Auto Review: Review", response["systemMessage"])

        review_dir = client_dir(project_root) / "reviews"
        review_path = sorted(review_dir.glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertIn("## Verdict", content)
        self.assertIn("Pending.", content)
        self.assertFalse(is_review_complete(review_path))

        log_path = client_dir(project_root) / "state.jsonl"
        log_content = log_path.read_text(encoding="utf-8")
        self.assertEqual(log_content.count("stop_hook_reviewer_empty"), 3)
        self.assertIn('"type":"stop_hook_reviewer_empty"', log_content)
        self.assertIn("stop_hook_reviewer_empty_blocked", log_content)
        self.assertNotIn('"type":"stop_approved"', log_content)

    def test_stop_hook_blocks_invalid_reviewer_backend(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        settings_dir = project_root / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"reviewerBackend": "codyx"}}),
            encoding="utf-8",
        )

        self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            input_text=json.dumps({"file_path": "src/app.ts"}),
        )

        stop = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            timeout=660,
        )

        self.assertEqual(stop.returncode, 2, stop.stderr)
        response = json.loads(stop.stdout.strip())
        self.assertEqual(response["decision"], "block")
        self.assertIn("invalid reviewerBackend setting", response["systemMessage"])
        self.assertIn("Unsupported reviewer backend: codyx", response["reason"])


if __name__ == "__main__":
    unittest.main()
