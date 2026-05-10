from claude_auto_review.paths import (
    DELETED_FILE_HASH,
    client_reviews_dir,
    client_run_dir,
    client_state_path,
    get_client_runtime_dir,
    get_client_id,
    get_log_path,
    get_plugin_root,
    get_project_root,
    get_state_path,
    normalize_relative_path,
    utc_now_iso,
)
from claude_auto_review.reviews import is_review_complete, pending_reviews_for_entries
import claude_auto_review.runtime as runtime
from claude_auto_review.settings import DEFAULT_SETTINGS, load_settings, should_skip_file
from claude_auto_review.state_store import (
    append_review_started,
    append_state,
    consecutive_stop_blocks,
    ensure_client_runtime,
    extract_file_paths_from_hook_input,
    get_file_hash,
    get_unreviewed_files,
    latest_entries_by_file,
    load_state,
    log_event,
    mark_files_reviewed,
    reviewed_hashes_by_file,
    was_hash_reviewed,
)


def ensure_runtime(project_root=None, plugin_root=None):
    return runtime.ensure_runtime(project_root, plugin_root)


def ensure_project_settings(project_root=None):
    return runtime.ensure_project_settings(project_root)


def cleanup_expired_pending_reviews(project_root=None, client_id=""):
    return runtime.cleanup_expired_pending_reviews(project_root, client_id)


def cancel_runtime(project_root=None, client_id=""):
    return runtime.cancel_runtime(project_root, client_id)


def cancel_session(project_root=None, client_id=""):
    return runtime.cancel_session(project_root, client_id)

