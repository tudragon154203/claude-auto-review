import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.state.records.edit import EditRecord  # noqa: E402
from claude_auto_review.state.store.write import append_state_event  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402
from tests.support_paths import client_dir  # noqa: E402


class TestReviewPrompt(HookTestCase, unittest.TestCase):
    def test_review_prompt_creates_prompt_and_allows_later_stop(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        review = self.run_python("claude_auto_review/review/prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        self.assertEqual(
            len(list((client_dir(project_root) / "run").iterdir())),
            1,
        )
        self.assertEqual(
            len(list((client_dir(project_root) / "reviews").iterdir())),
            1,
        )
        pending_stop = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            env_overrides={"PATH": ""},
            use_fake_claude=False,
        )
        self.assertEqual(pending_stop.returncode, 2)
        self.assertIn("Review", json.loads(pending_stop.stdout)["systemMessage"])
        self.complete_latest_review(project_root)
        self.assertEqual(
            self.run_python(
                "hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False
            ).returncode,
            0,
        )

    def test_includes_real_git_diff_content_in_generated_review_prompt(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=project_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_root, check=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=project_root, check=True)
        subprocess.run(["git", "add", "src/app.ts"], cwd=project_root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=project_root, check=True, capture_output=True, text=True)
        target.write_text("export const value = 2;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        review = self.run_python("claude_auto_review/review/prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        prompt = next((client_dir(project_root) / "run").glob("*prompt.md")).read_text(encoding="utf-8")
        self.assertIn("-export const value = 1;", prompt)
        self.assertIn("+export const value = 2;", prompt)

    def test_includes_session_diff_for_untracked_files_when_git_diff_is_empty(self):
        project_root = self.temp_project()
        (project_root / "src" / "new.ts").write_text("export const created = true;\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=project_root, check=True, capture_output=True, text=True)
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/new.ts"}))
        review = self.run_python("claude_auto_review/review/prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        prompt = next((client_dir(project_root) / "run").glob("*prompt.md")).read_text(encoding="utf-8")
        self.assertIn("## Session Diff", prompt)
        self.assertIn("## src/new.ts", prompt)
        self.assertIn("export const created = true;", prompt)

    def test_review_prompt_includes_custom_project_rules(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        rules_path = project_root / ".claude" / "claude-auto-review" / "review-rules.md"
        rules_path.write_text("# Custom Rules\n\n- Custom auth rule must appear.\n", encoding="utf-8")

        review = self.run_python("claude_auto_review/review/prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        prompt = next((client_dir(project_root) / "run").glob("*prompt.md")).read_text(encoding="utf-8")
        self.assertIn("Custom auth rule must appear.", prompt)

    def test_review_prompt_describes_deleted_tracked_file(self):
        project_root = self.temp_project()
        append_state_event(
            EditRecord(
                timestamp="2026-05-05T08:00:00+07:00",
                file="src/deleted.ts",
                hash="deadbeef",
                reviewed=False,
            ),
            project_root,
            client_id="test-session",
        )

        review = self.run_python("claude_auto_review/review/prompt.py", project_root)
        self.assertEqual(review.returncode, 0)
        prompt = next((client_dir(project_root) / "run").glob("*prompt.md")).read_text(encoding="utf-8")
        self.assertIn("## src/deleted.ts", prompt)
        self.assertIn("File does not currently exist.", prompt)


if __name__ == "__main__":
    unittest.main()
