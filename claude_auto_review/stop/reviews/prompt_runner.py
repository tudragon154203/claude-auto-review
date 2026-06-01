from __future__ import annotations

from typing import Callable

from claude_auto_review.config.models import DEFAULT_REVIEWER_MODEL
from claude_auto_review.runtime import process as _process_mod
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.reviews.cli_runner import run_review_cli
from claude_auto_review.stop.reviews.review_result import AutocompleteResult

# Exposed for test-patch compatibility (tests patch prompt_runner.run_captured)
run_captured = _process_mod.run_captured

# Re-export for backward compatibility; new code should import from cli_runner directly.
_run_review_cli = run_review_cli

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

    from .prompt_runner_codex import _attempt_codex_autocomplete
    from .prompt_runner_claude import _attempt_claude_autocomplete
    from .prompt_runner_opencode import _attempt_opencode_autocomplete

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
