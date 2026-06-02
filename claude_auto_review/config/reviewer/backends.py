"""Reviewer backend registry with injectable default registry.

`BackendRegistry` is the DIP-friendly abstraction that callers can inject
or extend. The module-level ``DEFAULT_REGISTRY`` keeps backward
compatibility for code that still uses the global mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Mapping

DEFAULT_REVIEWER_BACKEND = "claude"
DEFAULT_CLAUDE_REVIEWER_MODEL = "claude-sonnet-4-6"
DEFAULT_CODEX_REVIEWER_MODEL = "gpt-5.4-mini"
DEFAULT_OPENCODE_REVIEWER_MODEL = "opencode/big-pickle"


@dataclass(frozen=True)
class BackendRegistry:
    """Mapping of backend name -> default model.

    Use ``register()`` to add backends. ``clone()`` produces a copy that
    does not mutate shared state, which is useful for tests and for
    callers that want to pass an alternative registry explicitly.
    """

    _models: Mapping[str, str] = field(default_factory=dict)

    def names(self) -> frozenset[str]:
        return frozenset(self._models)

    def default_model(self, backend: str) -> str:
        return self._models[backend]

    def as_mapping(self) -> dict[str, str]:
        return dict(self._models)

    def register(self, name: str, default_model: str) -> BackendRegistry:
        updated = dict(self._models)
        updated[name] = default_model
        return BackendRegistry(_models=updated)

    def __contains__(self, name: str) -> bool:
        return name in self._models

    def __iter__(self) -> Iterator[str]:
        return iter(self._models)


def _default_backend_registry() -> BackendRegistry:
    return BackendRegistry(
        _models={
            "claude": DEFAULT_CLAUDE_REVIEWER_MODEL,
            "codex": DEFAULT_CODEX_REVIEWER_MODEL,
            "opencode": DEFAULT_OPENCODE_REVIEWER_MODEL,
        }
    )


DEFAULT_REGISTRY: BackendRegistry = _default_backend_registry()
DEFAULT_REVIEWER_MODELS = DEFAULT_REGISTRY.as_mapping()
REVIEWER_BACKENDS = DEFAULT_REGISTRY.names()
DEFAULT_REVIEWER_MODEL = DEFAULT_REVIEWER_MODELS[DEFAULT_REVIEWER_BACKEND]


def register_reviewer_backend(name: str, default_model: str) -> None:
    """Register a backend on the default registry (OCP extension point)."""
    global DEFAULT_REGISTRY, DEFAULT_REVIEWER_MODELS, REVIEWER_BACKENDS
    DEFAULT_REGISTRY = DEFAULT_REGISTRY.register(name, default_model)
    DEFAULT_REVIEWER_MODELS = DEFAULT_REGISTRY.as_mapping()
    REVIEWER_BACKENDS = DEFAULT_REGISTRY.names()


def resolve_reviewer_backend(reviewer_backend: str, *, registry: BackendRegistry | None = None) -> str:
    reg = registry or DEFAULT_REGISTRY
    if reviewer_backend not in reg:
        raise ValueError(f"Unsupported reviewer backend: {reviewer_backend}")
    return reviewer_backend


def resolve_reviewer_model(
    reviewer_model: str | None,
    *,
    backend: str,
    registry: BackendRegistry | None = None,
) -> str:
    if reviewer_model is not None:
        return reviewer_model
    reg = registry or DEFAULT_REGISTRY
    return reg.default_model(backend) if backend in reg else DEFAULT_REVIEWER_MODEL
