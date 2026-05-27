from __future__ import annotations

DEFAULT_REVIEWER_BACKEND = "claude"
DEFAULT_CLAUDE_REVIEWER_MODEL = "claude-sonnet-4-6"
DEFAULT_CODEX_REVIEWER_MODEL = "gpt-5.3-codex"
DEFAULT_REVIEWER_MODELS = {
    "claude": DEFAULT_CLAUDE_REVIEWER_MODEL,
    "codex": DEFAULT_CODEX_REVIEWER_MODEL,
}
DEFAULT_REVIEWER_MODEL = DEFAULT_REVIEWER_MODELS[DEFAULT_REVIEWER_BACKEND]
REVIEWER_BACKENDS = frozenset(DEFAULT_REVIEWER_MODELS)


def resolve_reviewer_backend(reviewer_backend: str) -> str:
    if reviewer_backend not in REVIEWER_BACKENDS:
        raise ValueError(f"Unsupported reviewer backend: {reviewer_backend}")
    return reviewer_backend


def resolve_reviewer_model(reviewer_model: str | None, *, backend: str) -> str:
    if reviewer_model is not None:
        return reviewer_model
    return DEFAULT_REVIEWER_MODELS.get(backend, DEFAULT_REVIEWER_MODEL)
