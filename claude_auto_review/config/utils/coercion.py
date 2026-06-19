from __future__ import annotations

from typing import Any

from claude_auto_review.config.constants.defaults import DEFAULT_RULES_FILE


def coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    return bool(value)


def coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def coerce_extensions(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(str(item) for item in value)


def coerce_rules_file(value: Any) -> str:
    """Normalize rulesFile paths to forward slashes for cross-platform compatibility.

    Backslash paths stored in .claude/settings.json on Windows (e.g.
    ``.claude\\claude-auto-review\\review-rules.md``) resolve correctly on
    Windows via pathlib but would fail on Unix where backslashes are treated
    as literal characters.  Normalizing to POSIX (forward-slash) form ensures
    the path works on both platforms.
    """
    if value is None:
        return DEFAULT_RULES_FILE
    text = str(value).strip()
    if not text:
        return DEFAULT_RULES_FILE
    return text.replace("\\", "/")
