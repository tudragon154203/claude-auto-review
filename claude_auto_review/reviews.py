from datetime import datetime, timezone
from pathlib import Path

from claude_auto_review.runtime_helpers import log_event


def _is_pending_review_entry(entry):
    return isinstance(entry, dict) and entry.get("type") == "review" and entry.get("status") == "pending"


def _pending_review_entries(state):
    for entry in state:
        if _is_pending_review_entry(entry):
            yield entry


def _pending_review_details(state, entries):
    needed = entry_file_hash_pairs(entries)
    for entry in _pending_review_entries(state):
        covered = review_file_hash_pairs(entry)
        overlap = needed & covered
        yield entry, needed, covered, overlap


def entry_file_hash_pairs(entries):
    return {
        (entry.get("file"), entry.get("hash"))
        for entry in entries
        if isinstance(entry, dict) and entry.get("file") and entry.get("hash")
    }


def review_file_hash_pairs(review_entry):
    return entry_file_hash_pairs(review_entry.get("files", []))


def is_review_expired(review_entry, timeout_hours):
    """Return True if a pending review is older than timeout_hours."""
    if timeout_hours <= 0:
        return False
    timestamp_str = review_entry.get("timestamp")
    if not timestamp_str:
        return False
    try:
        ts_str = timestamp_str
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0
        return age_hours > timeout_hours
    except (ValueError, TypeError):
        return False


def pending_reviews_for_entries(state, entries):
    matches = []
    for entry, needed, covered, overlap in _pending_review_details(state, entries):
        if needed and needed.issubset(covered):
            matches.append(entry)
    return sorted(matches, key=lambda e: e.get("timestamp", ""), reverse=True)


def pending_review_candidates_for_entries(state, entries, project_root=None, timeout_hours=0):
    """Return pending reviews that overlap the requested file/hash pairs.

    Matching semantics:
    - a review is eligible if it covers at least one requested file/hash pair
    - expired reviews are skipped
    - higher overlap wins, then newer timestamp wins
    """
    candidates = []
    for entry, _, _, overlap in _pending_review_details(state, entries):
        if timeout_hours > 0 and is_review_expired(entry, timeout_hours):
            log_event(
                project_root,
                "stop_review_expired",
                review_id=entry.get("reviewId", ""),
                files=[f.get("file", "") for f in entry.get("files", []) if isinstance(f, dict)],
            )
            continue
        if overlap:
            candidates.append({"review": entry, "overlap_count": len(overlap)})
    return sorted(candidates, key=lambda item: (item["overlap_count"], item["review"].get("timestamp", "")), reverse=True)


def best_pending_review_for_entries(state, entries, project_root=None, timeout_hours=0):
    candidates = pending_review_candidates_for_entries(state, entries, project_root=project_root, timeout_hours=timeout_hours)
    if not candidates:
        return None
    return candidates[0]["review"]


def is_review_complete(review_path):
    path = Path(review_path)
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8", errors="replace")
    if "## Verdict" not in content:
        return False
    verdict = content.split("## Verdict", 1)[1].strip()
    if not verdict:
        return False
    return verdict.lower() not in ("pending", "pending.")
