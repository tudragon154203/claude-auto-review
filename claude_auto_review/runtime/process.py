from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable


def run_captured(command: list[str] | str, *, cwd: str | Path, timeout: int | None = None, env: dict[str, str] | None = None, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        **kwargs,
    )


def _log_fail_open_error(project_root: str | Path | None, event_type: str | None, error: Exception, on_error: Callable[..., Any] | None, log_failure: Callable[..., Any]) -> None:
    handled = False
    if on_error is not None:
        try:
            handled = bool(on_error(error))
        except Exception as on_error_error:
            if event_type:
                log_failure(project_root, f"{event_type}_handler_failed", on_error_error, original_error=error)
    if event_type and not handled:
        log_failure(project_root, event_type, error)


def run_fail_open(callback: Callable[[], int], *, project_root: str | Path | None = None, event_type: str | None = None, on_error: Callable[..., Any] | None = None, fallback: int = 0, log_failure: Callable[..., Any] | None = None) -> int:
    if log_failure is None:
        from claude_auto_review.runtime.events import log_failure as _log_failure

        log_failure = _log_failure
    try:
        return callback()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        _log_fail_open_error(project_root, event_type, error, on_error, log_failure)
        return fallback
