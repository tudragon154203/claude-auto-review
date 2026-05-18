import os
import re
import socket
from datetime import datetime
from pathlib import Path

from claude_auto_review.paths.path_utils import CLIENTS_DIR, _project_root_path

_CLIENT_RUNTIME_DIR_PATTERN = re.compile(r"^client-(\d{8}-\d{6})_(.+)$")
_CLIENT_RUNTIME_DIR_CACHE = {}


def get_client_id(stdin_session_id=None) -> str:
    session_id = stdin_session_id or os.environ.get("CLAUDE_SESSION_ID")
    if session_id:
        return session_id

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    hostname = _safe_hostname()
    pid = os.getpid()
    return f"{ts}_{hostname}-{pid}"


def _safe_hostname():
    try:
        return socket.gethostname()
    except OSError:
        return "unknown"


def _client_runtime_dir_cache_key(project_root: Path, client_id: str):
    return str(project_root), client_id


def _cached_client_runtime_dir(cache_key):
    cached = _CLIENT_RUNTIME_DIR_CACHE.get(cache_key)
    if cached is None:
        return None
    if cached.exists() and cached.is_dir():
        return cached
    _CLIENT_RUNTIME_DIR_CACHE.pop(cache_key, None)
    return None


def _clear_client_runtime_dir_cache_entries(project_root: Path, client_id: str):
    cache_key = _client_runtime_dir_cache_key(project_root, client_id)
    _CLIENT_RUNTIME_DIR_CACHE.pop(cache_key, None)

    match = _CLIENT_RUNTIME_DIR_PATTERN.match(client_id)
    if match:
        bare_key = _client_runtime_dir_cache_key(project_root, match.group(2))
        _CLIENT_RUNTIME_DIR_CACHE.pop(bare_key, None)


def _timestamped_client_runtime_dir(project_root: Path, client_id: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return project_root / CLIENTS_DIR / f"client-{ts}_{client_id}"


def _find_existing_client_runtime_dir(project_root: Path, client_id: str):
    clients_dir = project_root / CLIENTS_DIR
    if not clients_dir.exists():
        return None

    timestamped = [
        child
        for child in clients_dir.iterdir()
        if child.is_dir()
        and (match := _CLIENT_RUNTIME_DIR_PATTERN.match(child.name))
        and match.group(2) == client_id
    ]
    if timestamped:
        return sorted(timestamped)[-1]
    return None


def get_existing_client_runtime_dir(project_root: Path, client_id: str) -> Path | None:
    project_root = _project_root_path(project_root)
    if _CLIENT_RUNTIME_DIR_PATTERN.match(client_id):
        direct = project_root / CLIENTS_DIR / client_id
        if direct.exists() and direct.is_dir():
            return direct
        return None
    return _find_existing_client_runtime_dir(project_root, client_id)


def get_client_runtime_dir(project_root: Path, client_id: str) -> Path:
    project_root = _project_root_path(project_root)
    cache_key = _client_runtime_dir_cache_key(project_root, client_id)
    cached = _cached_client_runtime_dir(cache_key)
    if cached is not None:
        return cached

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
    _clear_client_runtime_dir_cache_entries(project_root, client_id)


def client_state_path(project_root: Path, client_id: str) -> Path:
    return get_client_runtime_dir(project_root, client_id) / "state.jsonl"


def client_reviews_dir(project_root: Path, client_id: str) -> Path:
    return get_client_runtime_dir(project_root, client_id) / "reviews"


def client_run_dir(project_root: Path, client_id: str) -> Path:
    return get_client_runtime_dir(project_root, client_id) / "run"
