import os
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

STATE_RELATIVE_PATH = Path(".claude") / "claude-auto-review" / "state.jsonl"
RUNTIME_DIR = Path(".claude") / "claude-auto-review"
CLIENTS_DIR = RUNTIME_DIR / "clients"
LOG_RELATIVE_PATH = RUNTIME_DIR / "claude-auto-review.log"
DELETED_FILE_HASH = "__deleted__"


FILE_URI_PREFIX = "file://"
_CLIENT_RUNTIME_DIR_PATTERN = re.compile(r"^client-(\d{8}-\d{6})_(.+)$")


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
    it is used directly as the client_id. This ensures all hook invocations
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


_CLIENT_RUNTIME_DIR_CACHE = {}


def _client_runtime_dir_cache_key(project_root: Path, client_id: str):
    return str(project_root), client_id


def _timestamped_client_runtime_dir(project_root: Path, client_id: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return project_root / CLIENTS_DIR / f"client-{ts}_{client_id}"


def _find_existing_client_runtime_dir(project_root: Path, client_id: str):
    clients_dir = project_root / CLIENTS_DIR
    if not clients_dir.exists():
        return None

    timestamped = []
    for child in clients_dir.iterdir():
        if not child.is_dir():
            continue
        match = _CLIENT_RUNTIME_DIR_PATTERN.match(child.name)
        if match and match.group(2) == client_id:
            timestamped.append(child)

    if timestamped:
        return sorted(timestamped)[-1]
    return None


def get_client_runtime_dir(project_root: Path, client_id: str) -> Path:
    project_root = _project_root_path(project_root)
    cache_key = _client_runtime_dir_cache_key(project_root, client_id)
    cached = _CLIENT_RUNTIME_DIR_CACHE.get(cache_key)
    if cached is not None and cached.exists() and cached.is_dir():
        return cached
    if cached is not None:
        _CLIENT_RUNTIME_DIR_CACHE.pop(cache_key, None)

    if _CLIENT_RUNTIME_DIR_PATTERN.match(client_id):
        client_dir = project_root / CLIENTS_DIR / client_id
    else:
        client_dir = _find_existing_client_runtime_dir(project_root, client_id)
        if client_dir is None:
            client_dir = _timestamped_client_runtime_dir(project_root, client_id)

    _CLIENT_RUNTIME_DIR_CACHE[cache_key] = client_dir
    return client_dir


def invalidate_client_runtime_dir_cache(project_root: Path, client_id: str):
    project_root = _project_root_path(project_root)
    cache_key = _client_runtime_dir_cache_key(project_root, client_id)
    _CLIENT_RUNTIME_DIR_CACHE.pop(cache_key, None)
    match = _CLIENT_RUNTIME_DIR_PATTERN.match(client_id)
    if match:
        bare_key = _client_runtime_dir_cache_key(project_root, match.group(2))
        _CLIENT_RUNTIME_DIR_CACHE.pop(bare_key, None)


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
    file_path = _normalize_file_uri(os.fspath(file_path))
    project_root = _project_root_path(project_root)
    candidate = Path(file_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    try:
        relative = resolved.relative_to(project_root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return relative.as_posix()


def _normalize_file_uri(file_path: str) -> str:
    if not file_path.startswith(FILE_URI_PREFIX):
        return file_path
    parts = urlsplit(file_path)
    if parts.scheme != "file":
        return file_path
    if os.name == "nt" and parts.netloc and ":" in parts.netloc and not parts.path:
        return unquote(parts.netloc)
    path = unquote(parts.path or "")
    if parts.netloc and parts.netloc.lower() != "localhost":
        return f"//{parts.netloc}{path}"
    if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
        return path[1:]
    return path


def get_state_path(project_root=None):
    return _project_root_path(project_root) / STATE_RELATIVE_PATH


def get_log_path(project_root=None):
    return _project_root_path(project_root) / LOG_RELATIVE_PATH
