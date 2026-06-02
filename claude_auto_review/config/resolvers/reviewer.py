"""Reviewer backend and model resolution from plugin settings."""

from __future__ import annotations

from claude_auto_review.config.reviewer.backends import resolve_reviewer_backend, resolve_reviewer_model


def resolved_reviewer_backend(settings) -> str:
    return resolve_reviewer_backend(settings.reviewer_backend)


def resolved_reviewer_model(settings, *, backend: str | None = None) -> str:
    return resolve_reviewer_model(settings.reviewer_model, backend=backend or resolved_reviewer_backend(settings))
