from __future__ import annotations

DEFAULT_REVIEWER_BACKEND = "claude"
DEFAULT_CLAUDE_REVIEWER_MODEL = "claude-sonnet-4-6"
DEFAULT_CODEX_REVIEWER_MODEL = "gpt-5.4-mini"
DEFAULT_OPENCODE_REVIEWER_MODEL = "default"

_REVIEWER_BACKEND_REGISTRY: dict[str, str] = {
    "claude": DEFAULT_CLAUDE_REVIEWER_MODEL,
    "codex": DEFAULT_CODEX_REVIEWER_MODEL,
    "opencode": DEFAULT_OPENCODE_REVIEWER_MODEL,
}


def register_reviewer_backend(name: str, default_model: str) -> None:
    """Register a new reviewer backend — OCP extension point.

    Third-party integrations can call this at import time to add
    backends without modifying this module.
    """
    _REVIEWER_BACKEND_REGISTRY[name] = default_model


def _reviewer_backends() -> frozenset[str]:
    return frozenset(_REVIEWER_BACKEND_REGISTRY)


def _default_reviewer_models() -> dict[str, str]:
    return dict(_REVIEWER_BACKEND_REGISTRY)


DEFAULT_REVIEWER_MODELS = _REVIEWER_BACKEND_REGISTRY
REVIEWER_BACKENDS = _reviewer_backends()
DEFAULT_REVIEWER_MODEL = DEFAULT_REVIEWER_MODELS[DEFAULT_REVIEWER_BACKEND]


def resolve_reviewer_backend(reviewer_backend: str) -> str:
    if reviewer_backend not in _reviewer_backends():
        raise ValueError(f"Unsupported reviewer backend: {reviewer_backend}")
    return reviewer_backend


def resolve_reviewer_model(reviewer_model: str | None, *, backend: str) -> str:
    if reviewer_model is not None:
        return reviewer_model
    return _default_reviewer_models().get(backend, DEFAULT_REVIEWER_MODEL)
