import json
from pathlib import Path

from claude_auto_review.state.reviews.completion import is_review_complete
from claude_auto_review.state.store.queries import get_unreviewed_files
from claude_auto_review.state.store.read import load_state
from tests.e2e.support import EndToEndTestCase
from tests.support_paths import client_dir


class StopHookAutocompleteTestCase(EndToEndTestCase):
    def configure_codex_backend(self, project_root):
        (project_root / ".claude").mkdir(parents=True, exist_ok=True)
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"reviewerBackend": "codex"}}),
            encoding="utf-8",
        )

    def configure_opencode_backend(self, project_root):
        (project_root / ".claude").mkdir(parents=True, exist_ok=True)
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"reviewerBackend": "opencode"}}),
            encoding="utf-8",
        )

    def create_tracked_app(self, project_root):
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.track(project_root, "src/app.ts")

    def assert_stop_approved(self, stop):
        self.assertEqual(stop.returncode, 0, stop.stderr)
        approve = json.loads(stop.stdout.strip())
        self.assertNotIn("decision", approve)
        self.assertIn("Claude Auto Review", approve["systemMessage"])

    def latest_review_path(self, project_root):
        return sorted((client_dir(project_root) / "reviews").glob("review-*.md"))[-1]

    def assert_review_completed(self, project_root, expected_snippet=None):
        review_path = self.latest_review_path(project_root)
        content = review_path.read_text(encoding="utf-8")
        if expected_snippet is not None:
            self.assertIn(expected_snippet, content)
        self.assertTrue(
            is_review_complete(review_path),
            f"Expected completed review file, got:\n{content}",
        )

    def assert_prompt_contains_review_sections(self, prompt_path):
        prompt_text = Path(prompt_path).read_text(encoding="utf-8")
        self.assertIn("# Claude Auto Review Request", prompt_text)
        self.assertIn("## Session Diff", prompt_text)

    def assert_state_fully_reviewed(self, project_root):
        state = load_state(project_root, "test-session")
        self.assertTrue(state[-1].reviewed)
        self.assertEqual(len(get_unreviewed_files(state)), 0)

    def assert_fake_claude_run(self, project_root):
        run_dir = client_dir(project_root) / "run"
        prompts = list(run_dir.glob("review-*-prompt.md"))
        self.assertEqual(len(prompts), 1)

        capture = run_dir / "claude-cli-args.json"
        self.assertTrue(capture.exists(), "Fake claude should have captured its argv")
        cli_args = json.loads(capture.read_text(encoding="utf-8"))
        self.assertIn("--print", cli_args)
        self.assertIn("--model", cli_args)
        model_idx = cli_args.index("--model")
        self.assertEqual(cli_args[model_idx + 1], "claude-sonnet-4-6")
        self.assertIn("--allowedTools", cli_args)
        self.assertIn("--append-system-prompt-file", cli_args)
        prompt_idx = cli_args.index("--append-system-prompt-file")
        self.assert_prompt_contains_review_sections(cli_args[prompt_idx + 1])

    def assert_fake_codex_run(self, project_root):
        run_dir = client_dir(project_root) / "run"
        cli_args = json.loads((run_dir / "codex-cli-args.json").read_text(encoding="utf-8"))
        self.assertEqual(cli_args[:5], ["exec", "--skip-git-repo-check", "--sandbox", "read-only", "--model"])
        self.assertEqual(cli_args[5], "gpt-5.4-mini")
        self.assertIn("--output-last-message", cli_args)
        self.assertEqual(cli_args[-1], "-")

        stdin_text = (run_dir / "codex-cli-stdin.txt").read_text(encoding="utf-8")
        self.assertIn("# Claude Auto Review Request", stdin_text)
        self.assertIn("## Session Diff", stdin_text)
        self.assertIn("Complete the review", stdin_text)

        log_content = (client_dir(project_root) / "state.jsonl").read_text(encoding="utf-8")
        self.assertIn("stop_hook_reviewer_done", log_content)
        self.assertIn('"backend":"codex"', log_content)

    def assert_fake_opencode_run(self, project_root):
        run_dir = client_dir(project_root) / "run"
        cli_args = json.loads((run_dir / "opencode-cli-args.json").read_text(encoding="utf-8"))
        self.assertEqual(cli_args[0], "run")
        self.assertIn("--file", cli_args)
        file_idx = cli_args.index("--file")
        merged_path = Path(cli_args[file_idx + 1])
        self.assertTrue(str(merged_path).endswith("-merged-prompt.md"))

        log_content = (client_dir(project_root) / "state.jsonl").read_text(encoding="utf-8")
        self.assertIn("stop_hook_reviewer_done", log_content)
        self.assertIn('"backend":"opencode"', log_content)

    def assert_reviewer_done_logged(self, project_root, backend=None):
        log_content = (client_dir(project_root) / "state.jsonl").read_text(encoding="utf-8")
        self.assertIn("stop_hook_reviewer_done", log_content)
        if backend is not None:
            self.assertIn(f'"backend":"{backend}"', log_content)
