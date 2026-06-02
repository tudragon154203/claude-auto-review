import unittest

from claude_auto_review.paths.shell_parsing import (
    GIT_MOVE_SUBCOMMANDS,
    SHELL_CONTROL_TOKENS,
    SHELL_COPY_COMMANDS,
    SHELL_COPY_MOVE_COMMANDS,
    SHELL_MOVE_COMMANDS,
    SHELL_MULTI_ARG_COMMANDS,
    SHELL_PATH_COMMANDS,
    SHELL_REDIRECT_TOKENS,
    SHELL_WRAPPER_COMMAND_FLAGS,
    SHELL_WRAPPER_COMMANDS,
    SHELL_WRITE_COMMANDS,
)


class TestConstants(unittest.TestCase):
    def test_shell_control_tokens_is_set(self):
        self.assertIsInstance(SHELL_CONTROL_TOKENS, set)

    def test_shell_wrapper_commands_is_set(self):
        self.assertIsInstance(SHELL_WRAPPER_COMMANDS, set)

    def test_shell_redirect_tokens_is_set(self):
        self.assertIsInstance(SHELL_REDIRECT_TOKENS, set)

    def test_shell_multi_arg_commands_is_set(self):
        self.assertIsInstance(SHELL_MULTI_ARG_COMMANDS, set)

    def test_shell_copy_move_commands_is_set(self):
        self.assertIsInstance(SHELL_COPY_MOVE_COMMANDS, set)

    def test_shell_move_commands_is_set(self):
        self.assertIsInstance(SHELL_MOVE_COMMANDS, set)

    def test_shell_copy_commands_is_set(self):
        self.assertIsInstance(SHELL_COPY_COMMANDS, set)

    def test_git_move_subcommands_is_set(self):
        self.assertIsInstance(GIT_MOVE_SUBCOMMANDS, set)

    def test_copy_move_union_matches(self):
        self.assertEqual(SHELL_COPY_MOVE_COMMANDS, SHELL_MOVE_COMMANDS | SHELL_COPY_COMMANDS)

    def test_shell_write_commands_is_set(self):
        self.assertIsInstance(SHELL_WRITE_COMMANDS, set)

    def test_shell_path_commands_is_set(self):
        self.assertIsInstance(SHELL_PATH_COMMANDS, set)

    def test_shell_wrapper_command_flags_is_set(self):
        self.assertIsInstance(SHELL_WRAPPER_COMMAND_FLAGS, set)


if __name__ == "__main__":
    unittest.main()
