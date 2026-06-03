from __future__ import annotations

from claude_auto_review.config.resolvers.reviewer import resolved_reviewer_backend
from claude_auto_review.config.reviewer.backends import DEFAULT_REVIEWER_MODELS
from claude_auto_review.config.settings.models import PluginSettings
from claude_auto_review.config.utils.schema import (
    SETTING_MAX_STOP_PASSES,
    SETTING_MINIMUM_BLOCKING_SEVERITY,
    SETTING_REVIEWER_BACKEND,
    SETTING_REVIEWER_MODEL,
)


def _normalize_max_stop_passes(value: int) -> int:
    if value < 0:
        raise ValueError("maxStopPasses must be 0 or greater")
    return value


def _apply_args(settings: PluginSettings, args) -> PluginSettings:
    updated = settings.to_mapping()
    if args.backend:
        previous_backend = resolved_reviewer_backend(settings)
        known_default_models = set(DEFAULT_REVIEWER_MODELS.values())
        previous_default_model = DEFAULT_REVIEWER_MODELS[previous_backend]
        updated[SETTING_REVIEWER_BACKEND] = args.backend
        if not args.model and (
            settings.reviewer.reviewer_model is None
            or settings.reviewer.reviewer_model == previous_default_model
            or settings.reviewer.reviewer_model in known_default_models
        ):
            updated[SETTING_REVIEWER_MODEL] = DEFAULT_REVIEWER_MODELS[args.backend]
    if args.model:
        updated[SETTING_REVIEWER_MODEL] = args.model
    if args.severity:
        updated[SETTING_MINIMUM_BLOCKING_SEVERITY] = args.severity
    if args.max_stop_passes is not None:
        updated[SETTING_MAX_STOP_PASSES] = _normalize_max_stop_passes(args.max_stop_passes)
    return PluginSettings.from_mapping(updated)
