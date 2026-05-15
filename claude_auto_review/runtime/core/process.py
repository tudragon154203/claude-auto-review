import subprocess


def run_captured(command, *, cwd, timeout=None, env=None, **kwargs):
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


def _log_fail_open_error(project_root, event_type, error, on_error, log_failure):
    handled = False
    if on_error is not None:
        try:
            handled = bool(on_error(error))
        except Exception as on_error_error:
            if event_type:
                log_failure(project_root, f"{event_type}_handler_failed", on_error_error, original_error=error)
    if event_type and not handled:
        log_failure(project_root, event_type, error)


def run_fail_open(callback, *, project_root=None, event_type=None, on_error=None, fallback=0, log_failure=None):
    if log_failure is None:
        from claude_auto_review.runtime.core.events import log_failure as _log_failure

        log_failure = _log_failure
    try:
        return callback()
    except Exception as error:
        _log_fail_open_error(project_root, event_type, error, on_error, log_failure)
        return fallback
