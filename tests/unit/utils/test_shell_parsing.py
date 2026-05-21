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
    SHELL_WRITE_COMMANDS,
    SHELL_WRAPPER_COMMANDS,
    SHELL_WRAPPER_COMMAND_FLAGS,
    first_path_token,
    is_flag_token,
    normalize_command_token,
    non_flag_args,
    option_value,
    redirection_target,
    split_shell_segments,
    strip_quotes,
    tokenize_shell_command,
    wrapper_nested_command,
)


class TestStripQuotes(unittest.TestCase):
    def test_strips_double_quotes(self):
        self.assertEqual(strip_quotes('"hello"'), "hello")

    def test_strips_single_quotes(self):
        self.assertEqual(strip_quotes("'hello'"), "hello")

    def test_leaves_unquoted_string(self):
        self.assertEqual(strip_quotes("hello"), "hello")

    def test_leaves_empty_string(self):
        self.assertEqual(strip_quotes(""), "")

    def test_leaves_single_char(self):
        self.assertEqual(strip_quotes("a"), "a")

    def test_leaves_partial_quotes(self):
        self.assertEqual(strip_quotes('"hello'), '"hello')
        self.assertEqual(strip_quotes('hello"'), 'hello"')


class TestIsFlagToken(unittest.TestCase):
    def test_double_dash_flags(self):
        self.assertTrue(is_flag_token("--verbose"))
        self.assertTrue(is_flag_token("-v"))

    def test_single_slash_short_flags(self):
        self.assertTrue(is_flag_token("/c"))
        self.assertTrue(is_flag_token("/C"))

    def test_not_flag(self):
        self.assertFalse(is_flag_token("file.txt"))
        self.assertFalse(is_flag_token("my-flag"))  # no leading dash

    def test_long_slash_not_flag(self):
        self.assertFalse(is_flag_token("/command"))


class TestTokenizeShellCommand(unittest.TestCase):
    def test_simple_command(self):
        self.assertEqual(tokenize_shell_command("echo hello"), ["echo", "hello"])

    def test_quoted_arg(self):
        self.assertEqual(tokenize_shell_command('echo "hello world"'), ["echo", '"hello world"'])

    def test_empty_command(self):
        self.assertEqual(tokenize_shell_command(""), [])

    def test_malformed_quotes_returns_empty(self):
        self.assertEqual(tokenize_shell_command('echo "unclosed'), [])


class TestSplitShellSegments(unittest.TestCase):
    def test_splits_on_semicolon(self):
        self.assertEqual(split_shell_segments("echo a ; echo b"), [["echo", "a"], ["echo", "b"]])

    def test_splits_on_ampersand(self):
        self.assertEqual(split_shell_segments("echo a && echo b"), [["echo", "a"], ["echo", "b"]])

    def test_no_control_tokens_returns_single_segment(self):
        self.assertEqual(split_shell_segments("echo hello"), [["echo", "hello"]])

    def test_empty_command(self):
        self.assertEqual(split_shell_segments(""), [])

    def test_multiple_control_tokens(self):
        result = split_shell_segments("echo a ; echo b ; echo c")
        self.assertEqual(len(result), 3)


class TestNormalizeCommandToken(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(normalize_command_token("Echo"), "echo")

    def test_strips_quotes(self):
        self.assertEqual(normalize_command_token('"Echo"'), "echo")

    def test_already_lower(self):
        self.assertEqual(normalize_command_token("echo"), "echo")


class TestNonFlagArgs(unittest.TestCase):
    def test_filters_flags(self):
        self.assertEqual(non_flag_args(["-v", "file.txt"]), ["file.txt"])

    def test_filters_control_tokens(self):
        self.assertEqual(non_flag_args(["echo", ";", "file.txt"]), ["echo", "file.txt"])

    def test_filters_redirect_tokens(self):
        self.assertEqual(non_flag_args(["echo", ">", "file.txt"]), ["echo", "file.txt"])

    def test_returns_all_args_when_no_flags(self):
        self.assertEqual(non_flag_args(["file1.txt", "file2.txt"]), ["file1.txt", "file2.txt"])

    def test_empty_input(self):
        self.assertEqual(non_flag_args([]), [])


class TestWrapperNestedCommand(unittest.TestCase):
    def test_extracts_nested_with_c_flag(self):
        tokens = ["bash", "-c", "echo hello"]
        self.assertEqual(wrapper_nested_command(tokens), "echo hello")

    def test_extracts_nested_with_lc_flag(self):
        tokens = ["bash", "-lc", "echo hello"]
        self.assertEqual(wrapper_nested_command(tokens), "echo hello")

    def test_extracts_nested_with_slash_c_flag(self):
        tokens = ["cmd", "/c", "echo hello"]
        self.assertEqual(wrapper_nested_command(tokens), "echo hello")

    def test_no_wrapper_flag_returns_tail(self):
        tokens = ["bash", "echo hello"]
        self.assertEqual(wrapper_nested_command(tokens), "echo hello")

    def test_strips_quotes_from_nested(self):
        tokens = ["bash", "-c", '"echo hello"']
        self.assertEqual(wrapper_nested_command(tokens), "echo hello")

    def test_empty_after_flag_returns_none(self):
        tokens = ["bash", "-c", ""]
        self.assertIsNone(wrapper_nested_command(tokens))

    def test_single_token_returns_none(self):
        self.assertIsNone(wrapper_nested_command(["bash"]))

    def test_single_quote_wrapper_flag(self):
        tokens = ["bash", "-c", "'echo hello'"]
        self.assertEqual(wrapper_nested_command(tokens), "echo hello")


class TestRedirectionTarget(unittest.TestCase):
    def test_finds_redirect_target(self):
        self.assertEqual(redirection_target(["echo", ">", "file.txt"]), "file.txt")

    def test_finds_append_target(self):
        self.assertEqual(redirection_target(["echo", ">>", "file.txt"]), "file.txt")

    def test_returns_none_when_no_redirect(self):
        self.assertIsNone(redirection_target(["echo", "hello"]))

    def test_returns_none_when_redirect_is_last(self):
        self.assertIsNone(redirection_target(["echo", ">"]))

    def test_quoted_target(self):
        self.assertEqual(redirection_target(["echo", ">", '"file.txt"']), "file.txt")


class TestOptionValue(unittest.TestCase):
    def test_finds_simple_option_value(self):
        self.assertEqual(option_value(["-path", "C:\\test"], {"-path"}), "C:\\test")

    def test_finds_case_insensitive(self):
        self.assertEqual(option_value(["-Path", "C:\\test"], {"-path"}), "C:\\test")

    def test_returns_none_when_missing(self):
        self.assertIsNone(option_value(["-verbose"], {"-path"}))

    def test_returns_none_when_value_is_flag(self):
        self.assertIsNone(option_value(["-path", "-verbose"], {"-path"}))

    def test_returns_none_when_value_is_redirect(self):
        self.assertIsNone(option_value(["-path", ">", "file"], {"-path"}))

    def test_handles_quoted_values(self):
        self.assertEqual(option_value(["-path", '"C:\\test"'], {"-path"}), "C:\\test")


class TestFirstPathToken(unittest.TestCase):
    def test_returns_first_non_flag_non_control_token(self):
        self.assertEqual(first_path_token(["echo", "file.txt"]), "echo")

    def test_skips_flags(self):
        self.assertEqual(first_path_token(["-v", "file.txt"]), "file.txt")

    def test_skips_control_tokens(self):
        self.assertIsNone(first_path_token([";", "&&"]))

    def test_returns_none_for_empty(self):
        self.assertIsNone(first_path_token([]))

    def test_skips_redirect_tokens(self):
        self.assertIsNone(first_path_token([">", ">>"]))


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