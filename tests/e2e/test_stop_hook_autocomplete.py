import json
import unittest
from pathlib import Path

from claude_auto_review.state.reviews.verdicts import is_review_complete
from claude_auto_review.state.store.read import get_unreviewed_files, load_state
from tests.e2e.support import EndToEndTestCase
from tests.support import client_dir, real_claude_cli_available, real_codex_cli_available


class EndToEndStopHookAutocompleteTests(EndToEndTestCase):
    def test_stop_hook_auto_completes_review_with_fake_claude(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.track(project_root, "src/app.ts")

        stop = self.stop(project_root)
        self.assertEqual(stop.returncode, 0)
        approve = json.loads(stop.stdout.strip())
        self.assertNotIn("decision", approve)
        self.assertIn("Claude Auto Review", approve["systemMessage"])

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
        self.assertEqual(cli_args[idx + 1], "claude-sonnet-4-6")
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

    def test_stop_hook_auto_completes_review_with_fake_codex(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir(parents=True, exist_ok=True)
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"reviewerBackend": "codex"}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.track(project_root, "src/app.ts")

        stop = self.stop(project_root, use_fake_claude=False, use_fake_codex=True)
        self.assertEqual(stop.returncode, 0, stop.stderr)
        approve = json.loads(stop.stdout.strip())
        self.assertNotIn("decision", approve)
        self.assertIn("Claude Auto Review", approve["systemMessage"])

        _cd = client_dir(project_root)
        review_path = sorted((_cd / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertIn("Clean - no issues found. Claude may stop.", content)

        run_dir = _cd / "run"
        cli_args = json.loads((run_dir / "codex-cli-args.json").read_text(encoding="utf-8"))
        self.assertEqual(cli_args[:5], ["exec", "--json", "--sandbox", "read-only", "--model"])
        self.assertEqual(cli_args[5], "gpt-5.3-codex")
        self.assertEqual(cli_args[-1], "-")
        stdin_text = (run_dir / "codex-cli-stdin.txt").read_text(encoding="utf-8")
        self.assertIn("# Claude Auto Review Request", stdin_text)
        self.assertIn("## Current File Snapshots", stdin_text)
        self.assertIn("Complete the review", stdin_text)

        state = load_state(project_root, "test-session")
        self.assertTrue(state[-1].reviewed)
        self.assertEqual(len(get_unreviewed_files(state)), 0)

        log_path = client_dir(project_root) / "state.jsonl"
        self.assertIn("stop_hook_reviewer_done", log_path.read_text(encoding="utf-8"))
        self.assertIn('"backend":"codex"', log_path.read_text(encoding="utf-8"))

    @unittest.skipUnless(real_claude_cli_available(), "real claude CLI not available")
    def test_stop_hook_auto_completes_review_with_real_claude(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")
        stop = self.stop(project_root, use_fake_claude=False)
        self.assertEqual(stop.returncode, 0, stop.stderr)
        approve = json.loads(stop.stdout.strip())
        self.assertNotIn("decision", approve)
        self.assertIn("Claude Auto Review", approve["systemMessage"])

        _cd = client_dir(project_root)
        review_path = sorted((_cd / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertTrue(
            is_review_complete(review_path),
            f"Real claude should complete the review file, got:\n{content}",
        )

        log_path = client_dir(project_root) / "state.jsonl"
        self.assertIn("stop_hook_reviewer_done", log_path.read_text(encoding="utf-8"))

    @unittest.skipUnless(real_codex_cli_available(), "real codex CLI not available")
    def test_stop_hook_auto_completes_review_with_real_codex(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir(parents=True, exist_ok=True)
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"reviewerBackend": "codex"}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")
        stop = self.stop(project_root, use_fake_claude=False, use_fake_codex=False)
        self.assertEqual(stop.returncode, 0, stop.stderr)
        approve = json.loads(stop.stdout.strip())
        self.assertNotIn("decision", approve)
        self.assertIn("Claude Auto Review", approve["systemMessage"])

        _cd = client_dir(project_root)
        review_path = sorted((_cd / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        self.assertTrue(
            is_review_complete(review_path),
            f"Real codex should complete the review file, got:\n{content}",
        )

        log_path = client_dir(project_root) / "state.jsonl"
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn("stop_hook_reviewer_done", log_content)
        self.assertIn('"backend":"codex"', log_content)
