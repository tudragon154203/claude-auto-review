import os
import socket
from datetime import datetime, timezone
from pathlib import Path

STATE_RELATIVE_PATH = Path(".claude") / "claude-auto-review" / "state.jsonl"
RUNTIME_DIR = Path(".claude") / "claude-auto-review"
CLIENTS_DIR = RUNTIME_DIR / "clients"
LOG_RELATIVE_PATH = RUNTIME_DIR / "claude-auto-review.log"
DELETED_FILE_HASH = "__deleted__"


FILE_URI_PREFIX = "file://"


def local_now_iso():
    return datetime.now().astimezone().isoformat()



def get_project_root():
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()


def get_plugin_root():
    return Path(__file__).resolve().parent.parent


def get_reviewer_prompt_script():
    return get_plugin_root() / "review" / "prompt.py"


def _project_root_path(project_root=None):
    return Path(project_root or get_project_root()).resolve()


def get_client_id(stdin_session_id=None) -> str:
    """Returns a stable identifier for the current session.

    When a session_id is available (from stdin or CLAUDE_SESSION_ID),
    it used directly as the client_id. This ensures all hook invocations
    within the same session share the same client directory.

    When no session_id is available, a timestamp prefix is added to
    provide ordering and uniqueness (for standalone usage).
    """
    session_id = stdin_session_id or os.environ.get("CLAUDE_SESSION_ID")
    if session_id:
        return session_id

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "unknown"
    pid = os.getpid()
    return f"{ts}_{hostname}-{pid}"


def get_client_runtime_dir(project_root: Path, client_id: str) -> Path:
    return project_root / CLIENTS_DIR / f"client-{client_id}"


def client_state_path(project_root: Path, client_id: str) -> Path:
    return get_client_runtime_dir(project_root, client_id) / "state.jsonl"


def client_reviews_dir(project_root: Path, client_id: str) -> Path:
    return get_client_runtime_dir(project_root, client_id) / "reviews"


def client_run_dir(project_root: Path, client_id: str) -> Path:
    return get_client_runtime_dir(project_root, client_id) / "run"


def is_runtime_relative_path(file_path) -> bool:
    if not file_path:
        return False
    candidate = Path(os.fspath(file_path))
    try:
        relative = candidate.relative_to(RUNTIME_DIR)
    except ValueError:
        return False
    return bool(relative.parts)


def normalize_relative_path(file_path, project_root=None):
    if not file_path:
        return None
    file_path = os.fspath(file_path)
    project_root = _project_root_path(project_root)
    value = file_path[len(FILE_URI_PREFIX) :] if file_path.startswith(FILE_URI_PREFIX) else file_path
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    try:
        relative = resolved.relative_to(project_root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return relative.as_posix()


def get_state_path(project_root=None):
    return _project_root_path(project_root) / STATE_RELATIVE_PATH


def get_log_path(project_root=None):
    return _project_root_path(project_root) / LOG_RELATIVE_PATH
