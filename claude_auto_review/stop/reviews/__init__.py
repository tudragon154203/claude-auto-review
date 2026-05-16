from claude_auto_review.stop.reviews.core.prompt_runner import AutocompleteResult


def attempt_stop_autocomplete(*args, **kwargs):
    from claude_auto_review.stop.reviews.core.prompt_runner import attempt_stop_autocomplete as _impl

    return _impl(*args, **kwargs)


def find_pending_review_for_files(*args, **kwargs):
    from claude_auto_review.stop.reviews.core.selection import find_pending_review_for_files as _impl

    return _impl(*args, **kwargs)


def get_entries_covered_by_review(*args, **kwargs):
    from claude_auto_review.stop.reviews.core.selection import get_entries_covered_by_review as _impl

    return _impl(*args, **kwargs)

__all__ = [
    "AutocompleteResult",
    "attempt_stop_autocomplete",
    "find_pending_review_for_files",
    "get_entries_covered_by_review",
]
