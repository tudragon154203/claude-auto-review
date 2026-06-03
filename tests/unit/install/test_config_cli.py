import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.config.resolvers.reviewer import resolved_reviewer_model
from claude_auto_review.config.settings.models import PluginSettings, ReviewerSettings
from claude_auto_review.install.cli import config as config_cli


# ── shared helpers ────────────────────────────────────────────────────────────

def _make_initialized_project(tmp: str, plugin_settings=None):
    """Create a minimal initialized project under *tmp*.

    Sets up ``.claude/settings.json`` with hooks + plugin settings and writes
    ``review-rules.md`` so that ``_is_initialized`` returns True.

    Returns ``(project_root, settings_path)`` as ``Path`` objects.
    """
    project_root = Path(tmp)
    runtime_dir = project_root / ".claude" / "claude-auto-review"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "review-rules.md").write_text("# rules\n", encoding="utf-8")
    settings_path = project_root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    document = {"hooks": {"Stop": []}, "claude-auto-review": plugin_settings or {}}
    settings_path.write_text(json.dumps(document), encoding="utf-8")
    return project_root, settings_path


# ── test classes ──────────────────────────────────────────────────────────────

class TestConfigCli(unittest.TestCase):
    def test_severity_choices_use_semantic_order(self):
        self.assertEqual(config_cli.SEVERITY_CHOICES, ["info", "low", "medium", "high", "critical"])
        parser = config_cli._build_parser()
        severity_action = next(action for action in parser._actions if action.dest == "severity")
        self.assertEqual(list(severity_action.choices), config_cli.SEVERITY_CHOICES)

    def test_is_initialized_requires_runtime_rules_and_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            settings_path = project_root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps({"claude-auto-review": {}, "hooks": {"Stop": []}}),
                encoding="utf-8",
            )
            self.assertFalse(config_cli._is_initialized(project_root))

            runtime_dir = project_root / ".claude" / "claude-auto-review"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            self.assertFalse(config_cli._is_initialized(project_root))

            (runtime_dir / "review-rules.md").write_text("# rules\n", encoding="utf-8")
            self.assertTrue(config_cli._is_initialized(project_root))

    def test_apply_args_updates_selected_fields(self):
        settings = PluginSettings()
        args = config_cli._build_parser().parse_args(
            ["--backend", "codex", "--severity", "high", "--max-stop-passes", "7", "--non-interactive"]
        )

        updated = config_cli._apply_args(settings, args)

        self.assertEqual(updated.reviewer.reviewer_backend, "codex")
        self.assertEqual(resolved_reviewer_model(updated), "gpt-5.4-mini")
        self.assertEqual(updated.flow.minimum_blocking_severity, "high")
        self.assertEqual(updated.flow.max_stop_passes, 7)

    def test_apply_args_keeps_explicit_model_when_backend_changes(self):
        settings = PluginSettings(reviewer=ReviewerSettings(reviewer_model="custom-model"))
        args = config_cli._build_parser().parse_args(["--backend", "codex", "--non-interactive"])

        updated = config_cli._apply_args(settings, args)

        self.assertEqual(updated.reviewer.reviewer_backend, "codex")
        self.assertEqual(updated.reviewer.reviewer_model, "custom-model")

    def test_apply_args_replaces_old_backend_default_model(self):
        settings = PluginSettings(reviewer=ReviewerSettings(reviewer_backend="claude", reviewer_model="claude-sonnet-4-6"))
        args = config_cli._build_parser().parse_args(["--backend", "codex", "--non-interactive"])

        updated = config_cli._apply_args(settings, args)

        self.assertEqual(updated.reviewer.reviewer_backend, "codex")
        self.assertEqual(updated.reviewer.reviewer_model, "gpt-5.4-mini")

    def test_apply_args_switches_codex_default_back_to_claude_default(self):
        settings = PluginSettings(reviewer=ReviewerSettings(reviewer_backend="claude", reviewer_model="gpt-5.4-mini"))
        args = config_cli._build_parser().parse_args(["--backend", "claude", "--non-interactive"])

        updated = config_cli._apply_args(settings, args)

        self.assertEqual(updated.reviewer.reviewer_backend, "claude")
        self.assertEqual(updated.reviewer.reviewer_model, "claude-sonnet-4-6")

    def test_wizard_uses_claude_default_model_for_claude_backend(self):
        settings = PluginSettings(reviewer=ReviewerSettings(reviewer_backend="codex", reviewer_model="gpt-5.4-mini"))
        prompts = []

        def fake_input(prompt):
            prompts.append(prompt)
            return "" if len(prompts) > 1 else "claude"

        with patch("builtins.input", side_effect=fake_input):
            updated = config_cli._run_wizard(settings)

        self.assertEqual(updated.reviewer.reviewer_backend, "claude")
        self.assertEqual(updated.reviewer.reviewer_model, "claude-sonnet-4-6")
        self.assertTrue(any("Reviewer model (claude-sonnet-4-6)" in prompt for prompt in prompts))

    def test_wizard_prompts_for_important_settings_only(self):
        settings = PluginSettings()
        answers = iter(["codex", "my-model", "high", "8"])

        with patch("builtins.input", side_effect=lambda _: next(answers)):
            updated = config_cli._run_wizard(settings)

        self.assertEqual(updated.reviewer.reviewer_backend, "codex")
        self.assertEqual(updated.reviewer.reviewer_model, "my-model")
        self.assertEqual(updated.flow.minimum_blocking_severity, "high")
        self.assertEqual(updated.flow.max_stop_passes, 8)

    def test_wizard_accepts_defaults_on_empty_answers(self):
        settings = PluginSettings()

        with patch("builtins.input", side_effect=["", "", "", ""]):
            updated = config_cli._run_wizard(settings)

        self.assertEqual(updated.reviewer.reviewer_backend, settings.reviewer.reviewer_backend)
        self.assertEqual(resolved_reviewer_model(updated), resolved_reviewer_model(settings))
        self.assertEqual(updated.flow.minimum_blocking_severity, settings.flow.minimum_blocking_severity)
        self.assertEqual(updated.flow.max_stop_passes, settings.flow.max_stop_passes)

    def test_prompt_choice_retries_on_invalid_answer(self):
        stdout = io.StringIO()
        with patch("builtins.input", side_effect=["bad", "codex"]), patch("sys.stdout", stdout):
            result = config_cli._prompt_choice("Reviewer backend", ["claude", "codex"], "claude")

        self.assertEqual(result, "codex")
        self.assertIn("Please choose one of", stdout.getvalue())

    def test_prompt_int_retries_until_valid_non_negative_number(self):
        stdout = io.StringIO()
        with patch("builtins.input", side_effect=["abc", "-2", "9"]), patch("sys.stdout", stdout):
            result = config_cli._prompt_int("Max stop passes", 5)

        self.assertEqual(result, 9)
        output = stdout.getvalue()
        self.assertIn("Please enter a whole number.", output)
        self.assertIn("Please enter 0 or a positive number.", output)

    def test_print_advanced_settings_lists_non_wizard_keys(self):
        from claude_auto_review.config.settings.models import PluginSettings
        settings = PluginSettings()
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            config_cli._print_advanced_settings(Path("/tmp/settings.json"), settings)

        output = stdout.getvalue()
        self.assertIn("enabled", output)
        self.assertIn("rulesFile", output)
        self.assertIn("lastAssistantMessageClassifierEnabled", output)
        self.assertNotIn("reviewerBackend: Reviewer CLI backend\n", output)

    def test_main_initializes_then_updates_non_interactive(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            settings_path = project_root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(json.dumps({"other": {"keep": True}}), encoding="utf-8")

            runtime_dir = project_root / ".claude" / "claude-auto-review"

            def fake_runtime(_project_root):
                runtime_dir.mkdir(parents=True, exist_ok=True)
                (runtime_dir / "review-rules.md").write_text("# rules\n", encoding="utf-8")
                return {"base_dir": runtime_dir}

            def fake_project_settings(_project_root):
                document = json.loads(settings_path.read_text(encoding="utf-8"))
                document.setdefault("hooks", {"Stop": []})
                document.setdefault("claude-auto-review", {})
                settings_path.write_text(json.dumps(document), encoding="utf-8")
                return settings_path

            stdout = io.StringIO()
            with patch("claude_auto_review.install.cli.config.get_project_root", return_value=project_root), patch(
                "claude_auto_review.install.config.io.ensure_runtime", side_effect=fake_runtime
            ), patch(
                "claude_auto_review.install.config.io._settings_path", side_effect=fake_project_settings
            ), patch(
                "claude_auto_review.install.cli.config.log_event"
            ) as mock_log, patch("sys.stdout", stdout):
                result = config_cli.main(["--backend", "codex", "--severity", "high", "--max-stop-passes", "7", "--non-interactive"])

            self.assertEqual(result, 0)
            saved = json.loads(settings_path.read_text(encoding="utf-8"))
            plugin_settings = saved["claude-auto-review"]
            self.assertEqual(plugin_settings["reviewerBackend"], "codex")
            self.assertEqual(plugin_settings["reviewerModel"], "gpt-5.4-mini")
            self.assertEqual(plugin_settings["minimumBlockingSeverity"], "high")
            self.assertEqual(plugin_settings["maxStopPasses"], 7)
            self.assertEqual(saved["other"], {"keep": True})
            mock_log.assert_called_once_with(project_root, "config_updated", initialized=True)
            self.assertIn("initialized now", stdout.getvalue())
            self.assertIn("lastAssistantMessageClassifierEnabled", stdout.getvalue())

    def test_main_non_interactive_skips_wizard(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            runtime_dir = project_root / ".claude" / "claude-auto-review"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "review-rules.md").write_text("# rules\n", encoding="utf-8")
            settings_path = project_root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps({"hooks": {"Stop": []}, "claude-auto-review": {}}),
                encoding="utf-8",
            )

            with patch("claude_auto_review.install.cli.config.get_project_root", return_value=project_root), patch(
                "claude_auto_review.install.cli.config._run_wizard"
            ) as mock_wizard, patch("claude_auto_review.install.cli.config.log_event"):
                result = config_cli.main(["--non-interactive"])

            self.assertEqual(result, 0)
            mock_wizard.assert_not_called()

    def test_main_runs_wizard_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            runtime_dir = project_root / ".claude" / "claude-auto-review"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "review-rules.md").write_text("# rules\n", encoding="utf-8")
            settings_path = project_root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps({"hooks": {"Stop": []}, "claude-auto-review": {}}),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with patch("claude_auto_review.install.cli.config.get_project_root", return_value=project_root), patch(
                "builtins.input", side_effect=["", "", "", ""]
            ), patch("claude_auto_review.install.cli.config.log_event"), patch("sys.stdout", stdout):
                result = config_cli.main([])

            self.assertEqual(result, 0)
            self.assertIn("setup wizard", stdout.getvalue())

    def test_main_preserves_unrelated_settings_and_hooks_when_already_initialized(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            runtime_dir = project_root / ".claude" / "claude-auto-review"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "review-rules.md").write_text("# rules\n", encoding="utf-8")
            settings_path = project_root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(
                    {
                        "hooks": {"Stop": [{"hooks": [{"command": "python custom.py"}]}]},
                        "other": {"keep": True},
                        "claude-auto-review": {"reviewerBackend": "claude"},
                    }
                ),
                encoding="utf-8",
            )

            with patch("claude_auto_review.install.cli.config.get_project_root", return_value=project_root), patch(
                "claude_auto_review.install.cli.config.log_event"
            ):
                result = config_cli.main(["--backend", "codex", "--non-interactive"])

            self.assertEqual(result, 0)
            saved = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["other"], {"keep": True})
            self.assertEqual(saved["hooks"]["Stop"][0]["hooks"][0]["command"], "python custom.py")

    def test_main_wizard_after_flag_uses_flag_values_as_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            runtime_dir = project_root / ".claude" / "claude-auto-review"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "review-rules.md").write_text("# rules\n", encoding="utf-8")
            settings_path = project_root / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps({"hooks": {"Stop": []}, "claude-auto-review": {}}),
                encoding="utf-8",
            )

            with patch("claude_auto_review.install.cli.config.get_project_root", return_value=project_root), patch(
                "builtins.input", side_effect=["", "", "", ""]
            ), patch("claude_auto_review.install.cli.config.log_event"):
                result = config_cli.main(["--backend", "codex"])

            self.assertEqual(result, 0)
            saved = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["claude-auto-review"]["reviewerBackend"], "codex")
            self.assertEqual(saved["claude-auto-review"]["reviewerModel"], "gpt-5.4-mini")

    def test_wizard_shows_opencode_model_hint(self):
        settings = PluginSettings(reviewer=ReviewerSettings(reviewer_backend="opencode", reviewer_model="opencode/big-pickle"))
        stdout = io.StringIO()

        with patch("builtins.input", side_effect=["", "", "", ""]), patch("sys.stdout", stdout):
            config_cli._run_wizard(settings)

        self.assertIn("enter 'default' or 'none'", stdout.getvalue())

    def test_wizard_hides_model_hint_for_claude_backend(self):
        settings = PluginSettings(reviewer=ReviewerSettings(reviewer_backend="claude"))
        stdout = io.StringIO()

        with patch("builtins.input", side_effect=["", "", "", ""]), patch("sys.stdout", stdout):
            config_cli._run_wizard(settings)

        self.assertNotIn("enter 'default' or 'none'", stdout.getvalue())

    def test_wizard_hides_model_hint_for_codex_backend(self):
        settings = PluginSettings(reviewer=ReviewerSettings(reviewer_backend="codex"))
        stdout = io.StringIO()

        with patch("builtins.input", side_effect=["", "", "", ""]), patch("sys.stdout", stdout):
            config_cli._run_wizard(settings)

        self.assertNotIn("enter 'default' or 'none'", stdout.getvalue())

    def test_negative_max_stop_passes_is_rejected(self):
        with self.assertRaises(SystemExit):
            config_cli.main(["--max-stop-passes", "-1", "--non-interactive"])


if __name__ == "__main__":
    unittest.main()
