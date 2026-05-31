import json
import unittest

from claude_auto_review.state.store.queries import was_hash_reviewed
from claude_auto_review.state.store.read import load_state
from tests.int.hooks.support import HookTestCase
from tests.support_paths import client_dir


class TestStopFinalizationFindings(HookTestCase, unittest.TestCase):
    def test_stop_blocked_when_review_has_findings(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        verdict = "Not Clean - security issue found."
        findings = "Sensitive data logged to console."
        review_path = self.complete_latest_review(project_root, verdict=verdict)

        content = review_path.read_text(encoding="utf-8")
        new_content = content.replace(
            "No findings yet. This file is a placeholder until Claude completes the review.",
            findings,
        )
        review_path.write_text(new_content, encoding="utf-8")

        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2)
        self.assertIn("found issues to address.", stop2.stdout)
        self.assertIn(findings, stop2.stdout)

        state = load_state(project_root, "test-session")
        edit = next(entry for entry in state if getattr(entry, "file", None) == "src/app.ts")
        self.assertTrue(was_hash_reviewed(state, edit.file, edit.hash))

    def test_stop_blocked_when_review_is_incomplete_artifact(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        review_path = sorted((client_dir(project_root) / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        content = content.replace(
            "No findings yet. This file is a placeholder until Claude completes the review.",
            "The change introduces a potential regression in the retry logic.",
        )
        content = content.replace("Pending.", "Some completed artifact content without markers.")
        review_path.write_text(content, encoding="utf-8", newline="\n")

        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2)
        self.assertIn("found issues to address.", stop2.stdout)

    def test_stop_rewrites_contradictory_clean_verdict_when_findings_exist(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        findings = "### 1. Mutable shared state in helper\n**Severity:** Medium\n**Verdict:** Confirmed\n"
        review_path = self.complete_latest_review(
            project_root,
            verdict="Clean - no issues found. Claude may stop.",
        )
        content = review_path.read_text(encoding="utf-8")
        review_path.write_text(
            content.replace(
                "No findings yet. This file is a placeholder until Claude completes the review.",
                findings,
            ),
            encoding="utf-8",
            newline="\n",
        )

        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2)
        self.assertIn("found issues to address.", stop2.stdout)
        updated = review_path.read_text(encoding="utf-8")
        self.assertIn(
            "Findings present. Claude must address all findings before stopping.",
            updated,
        )
        self.assertNotIn("Clean - no issues found. Claude may stop.", updated)


if __name__ == "__main__":
    unittest.main()
