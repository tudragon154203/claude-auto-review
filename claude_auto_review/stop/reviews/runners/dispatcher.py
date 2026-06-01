from __future__ import annotations

from typing import Callable

from claude_auto_review.config.settings.models import DEFAULT_REVIEWER_MODEL
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.reviews.types.result import AutocompleteResult

AutocompleteFn = Callable[
    [RuntimeContext, str, object, object, str, int, str],
    AutocompleteResult,
]

_BACKEND_REGISTRY: dict[str, AutocompleteFn] = {}


def register_backend(name: str, fn: AutocompleteFn) -> None:
    _BACKEND_REGISTRY[name] = fn


def _register_default_backends() -> None:
    if _BACKEND_REGISTRY:
        return

    from .codex import _attempt_codex_autocomplete
    from .claude import _attempt_claude_autocomplete
    from .opencode import _attempt_opencode_autocomplete

    register_backend("codex", _attempt_codex_autocomplete)
    register_backend("claude", _attempt_claude_autocomplete)
    register_backend("opencode", _attempt_opencode_autocomplete)


def attempt_stop_autocomplete(
    ctx: RuntimeContext,
    review_id,
    review_path,
    prompt_file,
    user_prompt,
    reviewer_timeout_seconds=600,
    model=DEFAULT_REVIEWER_MODEL,
    backend="claude",
):
    _register_default_backends()
    fn = _BACKEND_REGISTRY.get(backend)
    if fn is None:
        raise ValueError(f"Unsupported reviewer backend: {backend}")
    return fn(ctx, review_id, review_path, prompt_file, user_prompt, reviewer_timeout_seconds, model)
