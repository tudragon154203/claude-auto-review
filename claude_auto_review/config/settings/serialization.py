from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from claude_auto_review.config.reviewer.backends import resolve_reviewer_model
from claude_auto_review.config.utils.schema import SETTING_SPECS, KNOWN_SETTING_KEYS, SETTING_REVIEWER_MODEL

if TYPE_CHECKING:
    from claude_auto_review.config.settings.models import PluginSettings


def plugin_settings_kwargs(mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(mapping) if isinstance(mapping, Mapping) else {}
    extras = {key: value for key, value in data.items() if key not in KNOWN_SETTING_KEYS}
    groups: dict[str, dict[str, Any]] = {
        "core": {},
        "reviewer": {},
        "classifier": {},
        "filters": {},
        "flow": {},
    }
    for spec in SETTING_SPECS:
        raw = data.get(spec.json_key)
        if spec.coerce_fn is not None:
            value = spec.coerce_fn(raw)
        elif raw is not None:
            value = raw
        elif spec.default is not None:
            value = spec.default
        else:
            continue
        group = spec.group
        groups[group][spec.field_name] = value
    from claude_auto_review.config.settings.models import (
        ClassifierSettings,
        CoreSettings,
        FilterSettings,
        FlowSettings,
        ReviewerSettings,
    )
    return {
        "core": CoreSettings(**groups["core"]),
        "reviewer": ReviewerSettings(**groups["reviewer"]),
        "classifier": ClassifierSettings(**groups["classifier"]),
        "filters": FilterSettings(**groups["filters"]),
        "flow": FlowSettings(**groups["flow"]),
        "extras": extras,
    }


def plugin_settings_mapping(settings: PluginSettings) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for spec in SETTING_SPECS:
        sub = getattr(settings, spec.group)
        value = getattr(sub, spec.field_name)
        if spec.to_mapping_transform is not None:
            value = spec.to_mapping_transform(value)
        if spec.json_key == SETTING_REVIEWER_MODEL:
            value = resolve_reviewer_model(value, backend=settings.reviewer.reviewer_backend)
        result[spec.json_key] = value
    result.update(settings.extras)
    return result
