#!/usr/bin/env python3
"""Entry point for the ``prompt`` subcommand and helper for the stop hook.

The orchestration is split into small, single-purpose steps
(``_ensure_review_environment``, ``_resolve_settings``, ``_query_unreviewed``,
``_handle_disabled``, ``_handle_noop``, ``_create_and_record_review``) so the
"god method" SRP violation is gone. The collaborators are also exposed via
``ReviewPromptDependencies`` for DIP-friendly injection.
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

if __name__ == "__main__":
    _plugin_root = Path(__file__).resolve().parents[2]
    if str(_plugin_root) not in sys.path:
        sys.path.insert(0, str(_plugin_root))

from claude_auto_review.config.io.settings_file import load_settings
from claude_auto_review.paths.path_utils import RUNTIME_DIR, ProjectContext
from claude_auto_review.paths.shims import write_project_script_shim
from claude_auto_review.review.prompting.flow import create_review_prompt_files
from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.runtime.events import log_event, log_failure
from claude_auto_review.runtime.process import run_fail_open
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.state.store.queries import get_unreviewed_files
from claude_auto_review.state.store.read import load_state_snapshot
from claude_auto_review.state.store.write import append_review_started
from claude_auto_review.stop.orchestration.types.context import RuntimeContext


@dataclass(frozen=True)
class ReviewPromptDependencies:
    ensure_runtime: Callable
    write_shim: Callable
    load_settings_fn: Callable
    snapshot_loader: Callable
    unreviewed_query: Callable
    create_artifacts: Callable
    append_started: Callable
    log_event_fn: Callable


def _log_failure(project_root, client_id, error):
    message = f"Claude Auto Review failed open: {error}"
    traceback_text = traceback.format_exc()
    if not log_failure(project_root, "review_prompt_error", client_id=client_id, error=error, traceback=traceback_text):
        print(message, file=sys.stderr)
        print(traceback_text, file=sys.stderr)
    else:
        print(message, file=sys.stderr)
    return True


def _ensure_review_environment(project_root, client_id, deps: ReviewPromptDependencies) -> None:
    deps.ensure_runtime(project_root, client_id)
    deps.write_shim(
        Path(project_root) / RUNTIME_DIR / "scripts" / "review_prompt.py",
        Path(__file__).resolve(),
    )


def _resolve_settings(project_root, deps: ReviewPromptDependencies):
    return deps.load_settings_fn(project_root)


def _query_unreviewed(project_root, client_id, deps: ReviewPromptDependencies):
    snapshot = deps.snapshot_loader(project_root, client_id)
    return deps.unreviewed_query(snapshot)


def _handle_disabled(project_root, client_id) -> int:
    log_event(project_root, "review_prompt_disabled", client_id=client_id)
    print("Claude Auto Review is disabled in .claude/settings.json.")
    return 0


def _handle_noop(project_root, client_id) -> int:
    log_event(project_root, "review_prompt_noop", client_id=client_id)
    print("Claude Auto Review: no unreviewed changes.")
    return 0


def _create_and_record_review(project_root, client_id, unreviewed, settings, deps: ReviewPromptDependencies) -> int:
    ctx = RuntimeContext(project_root=project_root, client_id=client_id, settings=settings)
    artifacts = deps.create_artifacts(ctx, unreviewed, settings=settings)
    deps.append_started(unreviewed, artifacts.review_id, artifacts.review_path, project_root, client_id=client_id)
    deps.log_event_fn(
        project_root,
        "review_prompt_created",
        client_id=client_id,
        reviewId=artifacts.review_id,
        files=artifacts.files,
        prompt=str(artifacts.prompt_path),
        review=str(artifacts.review_path),
    )
    print(f"Claude Auto Review prompt created: {artifacts.prompt_path}")
    print(f"Review file initialized: {artifacts.review_path}")
    print("Read the prompt, complete the review file, and fix all Confirmed findings before stopping.")
    return 0


def _current_module_deps() -> ReviewPromptDependencies:
    """Resolve dependencies from the current module namespace.

    This is patch-friendly: ``patch("claude_auto_review.review.prompt.<name>")``
    replaces the module attribute, and this factory reads it at call time.
    """
    import claude_auto_review.review.prompt as _mod
    return ReviewPromptDependencies(
        ensure_runtime=_mod.ensure_client_runtime,
        write_shim=_mod.write_project_script_shim,
        load_settings_fn=_mod.load_settings,
        snapshot_loader=_mod.load_state_snapshot,
        unreviewed_query=_mod.get_unreviewed_files,
        create_artifacts=_mod.create_review_prompt_files,
        append_started=_mod.append_review_started,
        log_event_fn=_mod.log_event,
    )


def _run_review_prompt(project_root, client_id, deps: ReviewPromptDependencies | None = None):
    deps = deps or _current_module_deps()
    _ensure_review_environment(project_root, client_id, deps)

    settings = _resolve_settings(project_root, deps)
    if not settings.core.enabled:
        return _handle_disabled(project_root, client_id)

    unreviewed = _query_unreviewed(project_root, client_id, deps)
    if not unreviewed:
        return _handle_noop(project_root, client_id)

    return _create_and_record_review(project_root, client_id, unreviewed, settings, deps)


def main():
    project_root = ProjectContext.from_environment().project_root

    def _run():
        client_id = get_client_id()
        return _run_review_prompt(project_root, client_id)

    return run_fail_open(_run, on_error=lambda error: _log_failure(project_root, None, error), fallback=1)


if __name__ == "__main__":
    raise SystemExit(main())
