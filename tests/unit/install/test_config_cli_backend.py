import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.install.cli import config as config_cli


class TestCheckBackendCli(unittest.TestCase):
    """Tests for _check_backend_cli output."""

    @patch("claude_auto_review.install.config.display.shutil.which", return_value="/usr/local/bin/claude")
    def test_found_prints_checkmark(self, mock_which):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            config_cli._check_backend_cli("claude")
        output = buf.getvalue()
        self.assertIn("claude CLI found", output)
        self.assertIn("/usr/local/bin/claude", output)
        self.assertNotIn("not found", output)

    @patch("claude_auto_review.install.config.display.shutil.which", return_value=None)
    def test_not_found_prints_warning_with_hint(self, mock_which):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            config_cli._check_backend_cli("codex")
        output = buf.getvalue()
        self.assertIn("⚠ codex CLI not found", output)
        self.assertIn("npm install -g @openai/codex", output)

    @patch("claude_auto_review.install.config.display.shutil.which", return_value=None)
    def test_not_found_claude_shows_claude_hint(self, mock_which):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            config_cli._check_backend_cli("claude")
        output = buf.getvalue()
        self.assertIn("npm install -g @anthropic-ai/claude-code", output)

    @patch("claude_auto_review.install.config.display.shutil.which", return_value=None)
    def test_not_found_opencode_shows_opencode_hint(self, mock_which):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            config_cli._check_backend_cli("opencode")
        output = buf.getvalue()
        self.assertIn("⚠ opencode CLI not found", output)
        self.assertIn("npm install -g opencode-ai", output)

    @patch("claude_auto_review.install.config.display.shutil.which", return_value="/usr/local/bin/opencode")
    def test_found_opencode_prints_checkmark(self, mock_which):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            config_cli._check_backend_cli("opencode")
        output = buf.getvalue()
        self.assertIn("opencode CLI found", output)
        self.assertIn("/usr/local/bin/opencode", output)

    @patch("claude_auto_review.install.config.display.shutil.which", return_value="/usr/bin/codex")
    def test_non_interactive_backend_flag_checks_cli(self, mock_which):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps({"claude-auto-review": {"enabled": True}}), encoding="utf-8"
            )
            buf = io.StringIO()
            with patch.object(config_cli, "get_project_root", return_value=Path(tmp)), \
                 patch.object(config_cli, "_is_initialized", return_value=True), \
                 patch.object(config_cli, "_write_plugin_settings", return_value=settings_path), \
                 patch("sys.stdout", buf):
                config_cli.main(["--backend", "codex", "--non-interactive"])
            self.assertIn("✓ codex CLI found", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
