import shutil

from claude_auto_review.paths import RUNTIME_DIR, client_state_path, get_client_runtime_dir
from claude_auto_review.reviews import is_review_expired
from claude_auto_review.runtime_helpers import log_event, resolve_client_id, resolve_project_root
from claude_auto_review.state_store_read import read_jsonl_records
from claude_auto_review.settings import load_settings


def cleanup_expired_pending_reviews(project_root=None, client_id=""):
    project_root = resolve_project_root(project_root)
    client_id = resolve_client_id(client_id)
    settings = load_settings(project_root)
    timeout_hours = float(settings.get("pendingReviewTimeoutHours", 1))

    state_path = client_state_path(project_root, client_id)
    if not state_path.exists():
        return 0

    entries = []
    removed = 0
    for line, entry in read_jsonl_records(state_path):
        if entry is None:
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
        log_event(project_root, "expired_reviews_cleaned", count=removed)
    return removed


def _remove_tree(target):
    try:
        if target.is_dir():
            shutil.rmtree(target)
            return True
        elif target.exists():
            target.unlink()
            return True
        return False
    except OSError:
        return False


def cancel_runtime(project_root=None, client_id=""):
    project_root = resolve_project_root(project_root)
    removed = []
    if client_id:
        client_dir = get_client_runtime_dir(project_root, client_id)
        if _remove_tree(client_dir):
            removed.append(client_dir)
        return removed
    runtime = project_root / RUNTIME_DIR
    if runtime.exists():
        for target in [
            runtime / "run",
            runtime / "reviews",
            runtime / "clients",
        ]:
            if _remove_tree(target):
                removed.append(target)
        try:
            if runtime.exists() and not any(runtime.iterdir()):
                runtime.rmdir()
                removed.append(runtime)
        except OSError:
            pass
    return removed


def cancel_session(project_root=None, client_id=""):
    project_root = resolve_project_root(project_root)
    client_id = resolve_client_id(client_id)
    client_dir = get_client_runtime_dir(project_root, client_id)
    removed = []
    if _remove_tree(client_dir):
        removed.append(client_dir)
        return removed
    return []

