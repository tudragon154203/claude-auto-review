import unittest
from unittest.mock import MagicMock, patch

from claude_auto_review import cli


class TestCliConfigRouting(unittest.TestCase):
    def test_config_subcommand_routes_to_config_module(self):
        module = MagicMock()
        module.main.return_value = 123

        with (
            patch("importlib.import_module", return_value=module) as mock_import,
            patch("sys.argv", ["claude-auto-review", "config", "--backend", "codex"]),
        ):
            result = cli.main()

        self.assertEqual(result, 123)
        mock_import.assert_called_once_with("claude_auto_review.install.config_cli")
        module.main.assert_called_once_with()

    def test_help_lists_config_subcommand(self):
        with patch("sys.argv", ["claude-auto-review", "--help"]), patch("builtins.print") as mock_print:
            result = cli.main()

        self.assertEqual(result, 0)
        printed = "\n".join(" ".join(str(arg) for arg in call.args) for call in mock_print.call_args_list)
        self.assertIn("config", printed)


if __name__ == "__main__":
    unittest.main()
