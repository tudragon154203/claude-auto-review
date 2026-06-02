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
from claude_auto_review.paths.path_utils import get_project_root
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

# Module-level aliases preserved so tests can patch collaborators via
# ``claude_auto_review.review.prompt.<name>``.
ensure_client_runtime = ensure_client_runtime
write_project_script_shim = write_project_script_shim
load_settings = load_settings
load_state_snapshot = load_state_snapshot
get_unreviewed_files = get_unreviewed_files
create_review_prompt_files = create_review_prompt_files
append_review_started = append_review_started
log_event = log_event
log_failure = log_failure
get_client_id = get_client_id
get_project_root = get_project_root


@dataclass(frozen=True)
class _ModuleAttributeDeps:
    """Lazy-binding dependency container.

    Each callable name is resolved against this module at call time, so
    tests that ``patch("claude_auto_review.review.prompt.<name>")`` after
    import still affect the dependency resolution.
    """

    def _resolve(self, name: str) -> Any:
        return globals()[name]

    @property
    def ensure_runtime(self):
        return self._resolve("ensure_client_runtime")

    @property
    def write_shim(self):
        return self._resolve("write_project_script_shim")

    @property
    def load_settings_fn(self):
        return self._resolve("load_settings")

    @property
    def snapshot_loader(self):
        return self._resolve("load_state_snapshot")

    @property
    def unreviewed_query(self):
        return self._resolve("get_unreviewed_files")

    @property
    def create_artifacts(self):
        return self._resolve("create_review_prompt_files")

    @property
    def append_started(self):
        return self._resolve("append_review_started")

    @property
    def log_event_fn(self):
        return self._resolve("log_event")


def _default_dependencies() -> _ModuleAttributeDeps:
    return _ModuleAttributeDeps()


def _log_failure(project_root, client_id, error):
    message = f"Claude Auto Review failed open: {error}"
    traceback_text = traceback.format_exc()
    if not log_failure(project_root, "review_prompt_error", client_id=client_id, error=error, traceback=traceback_text):
        print(message, file=sys.stderr)
        print(traceback_text, file=sys.stderr)
    else:
        print(message, file=sys.stderr)
    return True


def _ensure_review_environment(project_root, client_id, deps: _ModuleAttributeDeps) -> None:
    deps.ensure_runtime(project_root, client_id)
    deps.write_shim(
        Path(project_root) / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py",
        Path(__file__).resolve(),
    )


def _resolve_settings(project_root, deps: _ModuleAttributeDeps):
    return deps.load_settings_fn(project_root)


def _query_unreviewed(project_root, client_id, deps: _ModuleAttributeDeps):
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


def _create_and_record_review(project_root, client_id, unreviewed, settings, deps: _ModuleAttributeDeps) -> int:
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


def _run_review_prompt(project_root, client_id, deps: _ModuleAttributeDeps | None = None):
    deps = deps or _default_dependencies()
    _ensure_review_environment(project_root, client_id, deps)

    settings = _resolve_settings(project_root, deps)
    if not settings.core.enabled:
        return _handle_disabled(project_root, client_id)

    unreviewed = _query_unreviewed(project_root, client_id, deps)
    if not unreviewed:
        return _handle_noop(project_root, client_id)

    return _create_and_record_review(project_root, client_id, unreviewed, settings, deps)


def main():
    project_root = get_project_root()

    def _run():
        client_id = get_client_id()
        return _run_review_prompt(project_root, client_id)

    return run_fail_open(_run, on_error=lambda error: _log_failure(project_root, None, error), fallback=1)


if __name__ == "__main__":
    raise SystemExit(main())
