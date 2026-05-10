import json
import shutil
from pathlib import Path

from scripts.paths import RUNTIME_DIR, client_state_path, get_client_id, get_client_runtime_dir, get_project_root
from scripts.reviews import is_review_expired
from scripts.settings import load_settings


def _log_event(project_root, event_type, **kwargs):
    try:
        from scripts.paths import get_log_path, utc_now_iso

        log_path = get_log_path(project_root)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": utc_now_iso(), "event": event_type, **kwargs}
        with log_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass


def cleanup_expired_pending_reviews(project_root=None, client_id=""):
    project_root = Path(project_root or get_project_root())
    if not client_id:
        client_id = get_client_id()
    settings = load_settings(project_root)
    timeout_hours = float(settings.get("pendingReviewTimeoutHours", 1))

    state_path = client_state_path(project_root, client_id)
    if not state_path.exists():
        return 0

    entries = []
    removed = 0
    for line in state_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            entries.append(line)
            continue
        if (
            isinstance(entry, dict)
            and entry.get("type") == "review"
            and entry.get("status") == "pending"
            and is_review_expired(entry, timeout_hours)
        ):
            removed += 1
            continue
        entries.append(line)

    if removed > 0:
        with state_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(entries) + "\n")
        _log_event(project_root, "expired_reviews_cleaned", count=removed)
    return removed


def _remove_path(target, removed):
    try:
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(target)
        elif target.exists():
            target.unlink()
            removed.append(target)
    except OSError:
        pass


def cancel_runtime(project_root=None, client_id=""):
    project_root = Path(project_root or get_project_root())
    removed = []
    if client_id:
        client_dir = get_client_runtime_dir(project_root, client_id)
        if client_dir.exists():
            try:
                shutil.rmtree(client_dir)
                removed.append(client_dir)
            except OSError:
                pass
        return removed
    runtime = project_root / RUNTIME_DIR
    if runtime.exists():
        for target in [
            runtime / "run",
            runtime / "reviews",
            runtime / "clients",
        ]:
            _remove_path(target, removed)
        try:
            if runtime.exists() and not any(runtime.iterdir()):
                runtime.rmdir()
                removed.append(runtime)
        except OSError:
            pass
    return removed


def cancel_session(project_root=None, client_id=""):
    project_root = Path(project_root or get_project_root())
    if not client_id:
        client_id = get_client_id()
    client_dir = get_client_runtime_dir(project_root, client_id)
    if client_dir.exists():
        removed = []
        try:
            shutil.rmtree(client_dir)
            removed.append(client_dir)
        except OSError:
            pass
        return removed
    return []
