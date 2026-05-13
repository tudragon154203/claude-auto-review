import json
from pathlib import Path

from tests.e2e.support import EndToEndTestCase


class EndToEndMissingRulesTests(EndToEndTestCase):
    def test_no_rules_file_review_completes(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("const x = 1;\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")

        # Ensure no rules file exists
        rules_path = project_root / ".claude" / "claude-auto-review" / "review-rules.md"
        self.assertFalse(rules_path.exists())

        stop = self.stop(project_root)
        self.assertEqual(stop.returncode, 0)

    def test_empty_rules_file_review_completes(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("const x = 1;\n", encoding="utf-8")

        rules_path = project_root / ".claude" / "claude-auto-review" / "review-rules.md"
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        rules_path.write_text("", encoding="utf-8")

        self.track(project_root, "src/app.ts")

        stop = self.stop(project_root)
        self.assertEqual(stop.returncode, 0)

    def test_prompt_generated_without_rules_section(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("const x = 1;\n", encoding="utf-8")

        self.track(project_root, "src/app.ts")

        stop = self.stop(project_root, use_fake_claude=False, env_overrides={"PATH": ""})

        clients_dir = project_root / ".claude" / "claude-auto-review" / "clients"
        client_dirs = sorted(d for d in clients_dir.iterdir() if d.is_dir() and d.name.startswith("client-"))
        self.assertTrue(len(client_dirs) > 0, "Expected at least one client directory")
        prompts = sorted((client_dirs[0] / "run").glob("review-*-prompt.md"))
        self.assertTrue(len(prompts) > 0, "Expected at least one prompt file")

        prompt_content = prompts[-1].read_text(encoding="utf-8")
        self.assertIn("src/app.ts", prompt_content)
