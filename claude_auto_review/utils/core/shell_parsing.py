SHELL_CONTROL_TOKENS = {";", "&&", "||", "|"}
SHELL_REDIRECT_TOKENS = {">", ">>"}
SHELL_WRAPPER_COMMANDS = {"bash", "sh", "zsh", "fish", "cmd", "cmd.exe", "powershell", "pwsh"}
SHELL_WRAPPER_COMMAND_FLAGS = {"-c", "-lc", "/c", "-command"}
SHELL_MULTI_ARG_COMMANDS = {"rm", "del"}
SHELL_COPY_MOVE_COMMANDS = {"cp", "mv", "copy-item", "move-item"}
SHELL_DELETE_PS = "remove-item"
SHELL_WRITE_COMMANDS = {"cat", "echo", "printf"}
SHELL_PATH_COMMANDS = {"tee", "set-content", "out-file", "touch", "new-item"}


def strip_quotes(s):
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s


def is_flag_token(token):
    if token.startswith('-'):
        return True
    if token.startswith('/') and len(token) == 2 and token[1].isalpha():
        return True
    return False


def tokenize_shell_command(command):
    """Split a shell command string into tokens."""
    import shlex

    try:
        return shlex.split(command, posix=False)
    except ValueError:
        return []


def split_shell_segments(command):
    tokens = tokenize_shell_command(command)
    segments = []
    current = []
    for token in tokens:
        if token in SHELL_CONTROL_TOKENS:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def normalize_command_token(token):
    return strip_quotes(token).lower()


def non_flag_args(tokens):
    return [
        strip_quotes(token)
        for token in tokens
        if token not in SHELL_CONTROL_TOKENS and token not in SHELL_REDIRECT_TOKENS and not is_flag_token(strip_quotes(token))
    ]


def wrapper_nested_command(tokens):
    for index, token in enumerate(tokens[1:], start=1):
        if normalize_command_token(token) in SHELL_WRAPPER_COMMAND_FLAGS:
            nested = " ".join(tokens[index + 1 :]).strip()
            return strip_quotes(nested) if nested else None
    if len(tokens) > 1:
        nested = " ".join(tokens[1:]).strip()
        return strip_quotes(nested) if nested else None
    return None


def redirection_target(tokens):
    for index, token in enumerate(tokens):
        if token in SHELL_REDIRECT_TOKENS and index + 1 < len(tokens):
            target = strip_quotes(tokens[index + 1])
            if target and not is_flag_token(target):
                return target
    return None


def option_value(tokens, option_names):
    normalized = {name.lower() for name in option_names}
    for index, token in enumerate(tokens):
        if strip_quotes(token).lower() in normalized and index + 1 < len(tokens):
            value = strip_quotes(tokens[index + 1])
            if value and not is_flag_token(value) and value not in SHELL_REDIRECT_TOKENS:
                return value
    return None


def first_path_token(tokens):
    for token in tokens:
        cleaned = strip_quotes(token)
        if cleaned and not is_flag_token(cleaned) and cleaned not in SHELL_CONTROL_TOKENS and cleaned not in SHELL_REDIRECT_TOKENS:
            return cleaned
    return None
