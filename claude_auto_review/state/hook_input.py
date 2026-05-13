import shlex

_SHELL_CONTROL_TOKENS = {";", "&&", "||", "|"}
_SHELL_REDIRECT_TOKENS = {">", ">>"}
_SHELL_WRAPPER_COMMANDS = {"bash", "sh", "zsh", "fish", "cmd", "cmd.exe", "powershell", "pwsh"}
_SHELL_WRAPPER_COMMAND_FLAGS = {"-c", "-lc", "/c", "-command"}
_SHELL_MULTI_ARG_COMMANDS = {"rm", "del"}
_SHELL_COPY_MOVE_COMMANDS = {"cp", "mv", "copy-item", "move-item"}
_SHELL_DELETE_PS = "remove-item"
_SHELL_WRITE_COMMANDS = {"cat", "echo", "printf"}
_SHELL_PATH_COMMANDS = {"tee", "set-content", "out-file", "touch", "new-item"}


def _strip_quotes(s):
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s


def _is_flag_token(token):
    if token.startswith('-'):
        return True
    if token.startswith('/') and len(token) == 2 and token[1].isalpha():
        return True
    return False


def _tokenize_shell_command(command):
    try:
        return shlex.split(command, posix=False)
    except ValueError:
        return []


def _split_shell_segments(command):
    segments = []
    current = []
    for token in _tokenize_shell_command(command):
        if token in _SHELL_CONTROL_TOKENS:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def _normalize_command_token(token):
    return _strip_quotes(token).lower()


def _non_flag_args(tokens):
    return [
        _strip_quotes(token)
        for token in tokens
        if token not in _SHELL_CONTROL_TOKENS and token not in _SHELL_REDIRECT_TOKENS and not _is_flag_token(_strip_quotes(token))
    ]


def _wrapper_nested_command(tokens):
    for index, token in enumerate(tokens[1:], start=1):
        if _normalize_command_token(token) in _SHELL_WRAPPER_COMMAND_FLAGS:
            nested = " ".join(tokens[index + 1 :]).strip()
            return _strip_quotes(nested) if nested else None
    if len(tokens) > 1:
        nested = " ".join(tokens[1:]).strip()
        return _strip_quotes(nested) if nested else None
    return None


def _redirection_target(tokens):
    for index, token in enumerate(tokens):
        if token in _SHELL_REDIRECT_TOKENS and index + 1 < len(tokens):
            target = _strip_quotes(tokens[index + 1])
            if target and not _is_flag_token(target):
                return target
    return None


def _option_value(tokens, option_names):
    normalized = {name.lower() for name in option_names}
    for index, token in enumerate(tokens):
        if _strip_quotes(token).lower() in normalized and index + 1 < len(tokens):
            value = _strip_quotes(tokens[index + 1])
            if value and not _is_flag_token(value) and value not in _SHELL_REDIRECT_TOKENS:
                return value
    return None


def _first_path_token(tokens):
    for token in tokens:
        cleaned = _strip_quotes(token)
        if cleaned and not _is_flag_token(cleaned) and cleaned not in _SHELL_CONTROL_TOKENS and cleaned not in _SHELL_REDIRECT_TOKENS:
            return cleaned
    return None


def _append_path_candidate(candidates, value):
    if isinstance(value, str) and value.strip():
        candidates.append(value)


def _extract_paths_from_shell_command(command):
    if not isinstance(command, str) or not command.strip():
        return []

    paths = []

    for tokens in _split_shell_segments(command):
        if not tokens:
            continue
        command_name = _normalize_command_token(tokens[0])
        if command_name in _SHELL_WRAPPER_COMMANDS:
            nested = _wrapper_nested_command(tokens)
            if nested:
                paths.extend(_extract_paths_from_shell_command(nested))
            continue

        if command_name in _SHELL_MULTI_ARG_COMMANDS or command_name == _SHELL_DELETE_PS:
            paths.extend(_non_flag_args(tokens[1:]))
            continue

        if command_name in _SHELL_COPY_MOVE_COMMANDS:
            args = _non_flag_args(tokens[1:])
            if len(args) >= 2:
                paths.append(args[-1])
            elif args:
                paths.append(args[0])
            continue

        if command_name in _SHELL_WRITE_COMMANDS:
            target = _redirection_target(tokens[1:])
            if target:
                paths.append(target)
            continue

        if command_name in _SHELL_PATH_COMMANDS:
            target = _option_value(tokens[1:], {"-path", "-literalpath", "-destination"})
            if target is None:
                target = _first_path_token(tokens[1:])
            if target:
                paths.append(target)
            continue

    return paths


def _path_candidates_from_mapping(mapping):
    candidates = []
    if not isinstance(mapping, dict):
        return candidates

    for key in ("file_path", "path", "filePath"):
        _append_path_candidate(candidates, mapping.get(key))

    edits = mapping.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                for key in ("file_path", "path", "filePath"):
                    _append_path_candidate(candidates, edit.get(key))

    for key in ("command", "script"):
        command = mapping.get(key)
        if command:
            candidates.extend(_extract_paths_from_shell_command(command))

    return candidates


def _unique_strings(values):
    seen = set()
    unique = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def extract_file_paths_from_hook_input(payload):
    tool_input = payload.get("tool_input", payload) if isinstance(payload, dict) else {}
    candidates = _path_candidates_from_mapping(tool_input)
    return _unique_strings(candidates)
