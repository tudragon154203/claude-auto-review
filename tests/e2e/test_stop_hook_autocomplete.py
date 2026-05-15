import json
import sys
import unittest
from pathlib import Path

from tests.e2e.support import EndToEndTestCase
from tests.support import real_cli_available

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from claude_auto_review.state.store_read import get_unreviewed_files, load_state
from claude_auto_review.state.reviews import is_review_complete
from tests.support import client_dir


class EndToEndStopHookAutocompleteTests(EndToEndTestCase):
    def test_stop_hook_auto_completes_review_with_fake_claude(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.track(project_root, "src/app.ts")

        stop = self.stop(project_root)
        self.assertEqual(stop.returncode, 0)
        self.assertEqual(stop.stdout.strip(), "")

        _cd = client_dir(project_root)
        review_path = sorted((_cd / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertIn("Clean - no issues found. Claude may stop.", content)

        prompts = list((_cd / "run").glob("review-*-prompt.md"))
        self.assertEqual(len(prompts), 1)

        capture = _cd / "run" / "claude-cli-args.json"
        self.assertTrue(capture.exists(), "Fake claude should have captured its argv")
        cli_args = json.loads(capture.read_text(encoding="utf-8"))
        self.assertIn("--print", cli_args)
        self.assertIn("--model", cli_args)
        idx = cli_args.index("--model")
        self.assertEqual(cli_args[idx + 1], "fast")
        self.assertIn("--allowedTools", cli_args)
        self.assertIn("--append-system-prompt-file", cli_args)
        prompt_idx = cli_args.index("--append-system-prompt-file")
        prompt_arg = cli_args[prompt_idx + 1]
        self.assertTrue(prompt_arg.endswith("-prompt.md"))
        prompt_text = Path(prompt_arg).read_text(encoding="utf-8")
        self.assertIn("# Claude Auto Review Request", prompt_text)
        self.assertIn("## Current File Snapshots", prompt_text)

        state = load_state(project_root, "test-session")
        self.assertTrue(state[-1].reviewed)
        self.assertEqual(len(get_unreviewed_files(state)), 0)

    @unittest.skipUnless(real_cli_available(), "real claude CLI not available")
    def test_stop_hook_auto_completes_review_with_real_claude(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")
        stop = self.stop(project_root, use_fake_claude=False)
        self.assertEqual(stop.returncode, 0, stop.stderr)
        self.assertEqual(stop.stdout.strip(), "")

        _cd = client_dir(project_root)
        review_path = sorted((_cd / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertTrue(
            is_review_complete(review_path),
            f"Real claude should complete the review file, got:\n{content}",
        )

        log_path = project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log"
        self.assertIn("stop_hook_claude_cli_done", log_path.read_text(encoding="utf-8"))
