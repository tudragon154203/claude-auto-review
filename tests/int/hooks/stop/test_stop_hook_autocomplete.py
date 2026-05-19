#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.state.reviews.verdicts import is_review_complete  # noqa: E402
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

        self.assertEqual(stop.returncode, 0, f"stop should succeed; stdout={stop.stdout[:200]}; stderr={stop.stderr[:200]}")
        approve = json.loads(stop.stdout.strip())
        self.assertEqual(approve["decision"], "approve")

        review_dir = client_dir(project_root) / "reviews"
        review_path = sorted(review_dir.glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertIn("## Verdict", content)
        self.assertNotIn("Pending.", content)
        self.assertTrue(is_review_complete(review_path))

        log_path = client_dir(project_root) / "state.jsonl"
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn("stop_hook_claude_cli_done", log_content)


if __name__ == "__main__":
    unittest.main()

