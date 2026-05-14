from claude_auto_review.paths import get_client_id as _get_client_id, get_log_path as _get_log_path, get_project_root as _get_project_root
from claude_auto_review.runtime.context import (
    get_payload_session_id as _get_payload_session_id,
    read_json_payload as _read_json_payload,
    resolve_client_id as _resolve_client_id,
    resolve_project_root as _resolve_project_root,
)
from claude_auto_review.runtime.events import log_event as _log_event, log_failure as _log_failure
from claude_auto_review.runtime.process import run_captured as _run_captured, run_fail_open as _run_fail_open


def get_project_root():
    return _get_project_root()


def get_client_id(stdin_session_id=None):
    return _get_client_id(stdin_session_id)


def get_log_path(project_root=None):
    return _get_log_path(project_root)


def resolve_project_root(project_root=None):
    return _resolve_project_root(project_root)


def resolve_client_id(client_id=""):
    return _resolve_client_id(client_id)


def read_json_payload(raw):
    return _read_json_payload(raw)


def log_event(project_root, event_type, **kwargs):
    return _log_event(project_root, event_type, **kwargs)


def log_failure(project_root, event_type, error, **kwargs):
    return _log_failure(project_root, event_type, error, **kwargs)


def get_payload_session_id(payload):
    return _get_payload_session_id(payload)


def run_captured(command, *, cwd, timeout=None, env=None, **kwargs):
    return _run_captured(command, cwd=cwd, timeout=timeout, env=env, **kwargs)


def run_fail_open(callback, *, project_root=None, event_type=None, on_error=None, fallback=0):
    return _run_fail_open(
        callback,
        project_root=project_root,
        event_type=event_type,
        on_error=on_error,
        fallback=fallback,
        log_failure=log_failure,
    )
