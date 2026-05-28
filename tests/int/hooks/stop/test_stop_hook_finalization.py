import json
import unittest

from claude_auto_review.state.store.read import load_state, was_hash_reviewed
from tests.int.hooks.support import HookTestCase
from tests.support import client_dir, start_classifier_server


class TestStopHookFinalization(HookTestCase, unittest.TestCase):
    def test_stop_blocked_when_review_has_findings(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        # 1. Track edit
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        # 2. First stop creates pending review
        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        # 3. Complete review with findings
        verdict = "Not Clean - security issue found."
        findings = "Sensitive data logged to console."
        review_path = self.complete_latest_review(project_root, verdict=verdict)

        # Inject findings into the review file
        content = review_path.read_text(encoding="utf-8")
        new_content = content.replace(
            "No findings yet. This file is a placeholder until Claude completes the review.",
            findings,
        )
        review_path.write_text(new_content, encoding="utf-8")

        # 4. Second stop should still block because of findings
        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2)
        self.assertIn("found issues to address.", stop2.stdout)
        self.assertIn(findings, stop2.stdout)

        state = load_state(project_root, "test-session")
        edit = next(entry for entry in state if getattr(entry, "file", None) == "src/app.ts")
        self.assertTrue(was_hash_reviewed(state, edit.file, edit.hash))

    def test_stop_blocked_when_review_is_incomplete_artifact(self):
        """Test the path where is_completed_review_content is True but there is no full verdict."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        # 1. Track edit
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        # 2. First stop creates pending review
        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        # 3. Overwrite review so it looks completed but carries no verdict
        review_path = sorted((client_dir(project_root) / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        # Replace the placeholder "no findings" text with a finding so the
        # review looks like a completed-but-not-clean artifact.
        content = content.replace(
            "No findings yet. This file is a placeholder until Claude completes the review.",
            "The change introduces a potential regression in the retry logic.",
        )
        content = content.replace("Pending.", "Some completed artifact content without markers.")
        review_path.write_text(content, encoding="utf-8", newline="\n")

        # 4. Second stop should still block
        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2)
        self.assertIn("found issues to address.", stop2.stdout)

    def test_stop_rewrites_contradictory_clean_verdict_when_findings_exist(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        findings = "### 1. Mutable shared state in helper\n" "**Severity:** Medium\n" "**Verdict:** Confirmed\n"
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

    def test_stop_allows_findings_below_configured_threshold(self):
        project_root = self.temp_project()
        settings_dir = project_root / ".claude"
        settings_dir.mkdir(parents=True, exist_ok=True)
        (settings_dir / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"minimumBlockingSeverity": "high"}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        review_path = self.complete_latest_review(project_root, verdict="Clean - no issues found. Claude may stop.")
        content = review_path.read_text(encoding="utf-8")
        review_path.write_text(
            content.replace(
                "No findings yet. This file is a placeholder until Claude completes the review.",
                "### 1. [Medium] Advisory issue\n**Verdict:** Confirmed\n",
            ),
            encoding="utf-8",
            newline="\n",
        )

        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 0)

    def test_stop_allowed_when_classifier_overrides_blocking(self):
        """Classifier says 'incomplete' → stop is allowed even when review is pending."""
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        server, base_url = start_classifier_server("incomplete")
        try:
            payload = json.dumps({"last_assistant_message": "I will finish this later."})
            result = self.run_python(
                "hooks/stop_hook.py",
                project_root,
                input_text=payload,
                env_overrides={
                    "ANTHROPIC_BASE_URL": base_url,
                    "ANTHROPIC_API_KEY": "secret-key",
                    "PATH": "",
                },
                use_fake_claude=False,
            )
            self.assertEqual(result.returncode, 0)
        finally:
            server.shutdown()
            server.server_close()

    def test_partial_review_allowed_when_classifier_overrides_blocking(self):
        """Classifier 'incomplete' → allowed to stop even when review is clean but partial."""
        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("a", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("b", encoding="utf-8")

        # 1. Edit a.ts
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/a.ts"}))

        # 2. First stop creates a review covering a.ts
        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        # 3. New edit for b.ts → review is now partial
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))

        # 4. Mark a.ts review clean
        self.complete_latest_review(project_root, verdict="Clean - no issues found. Claude may stop.")

        # 5. Classifier says incomplete → allow stop
        server, base_url = start_classifier_server("incomplete")
        try:
            payload = json.dumps({"last_assistant_message": "Stopping now, b.ts will be reviewed later."})
            result = self.run_python(
                "hooks/stop_hook.py",
                project_root,
                input_text=payload,
                env_overrides={
                    "ANTHROPIC_BASE_URL": base_url,
                    "ANTHROPIC_API_KEY": "secret-key",
                    "PATH": "",
                },
                use_fake_claude=False,
            )
            self.assertEqual(result.returncode, 0)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
