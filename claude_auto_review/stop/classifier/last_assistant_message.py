from __future__ import annotations

import os
import time
from typing import Callable

from claude_auto_review.stop.classifier.client import call_classifier_api, sanitize_base_url
from claude_auto_review.stop.classifier.enums import ClassifierReason, ClassifierStatus
from claude_auto_review.stop.classifier.extraction import extract_last_assistant_message_text
from claude_auto_review.stop.classifier.models import (
    result_factory,
)
from claude_auto_review.stop.orchestration.types.context import RuntimeContext


def _validate_classifier_env(env) -> tuple[str, str]:
    base_url = sanitize_base_url(env.get("ANTHROPIC_BASE_URL", ""))
    api_key = env.get("ANTHROPIC_API_KEY", "")
    return base_url, api_key


def _extract_message_text(ctx: RuntimeContext, *, started_at: float, persist: Callable | None) -> tuple[str, int] | None:
    message_text = extract_last_assistant_message_text(ctx.payload)
    message_chars = len(message_text)
    if not message_text:
        result = result_factory(ClassifierStatus.SKIPPED, ClassifierReason.MISSING_MESSAGE, started_at, 0)
        if persist is not None:
            persist(result)
        return None
    return message_text, message_chars


def classify_last_assistant_message(
    ctx: RuntimeContext,
    env=None,
    urlopen=None,
    *,
    persist: Callable | None = None,
):
    if not ctx.settings.last_assistant_message_classifier_enabled:
        return None

    started_at = time.monotonic()

    extracted = _extract_message_text(ctx, started_at=started_at, persist=persist)
    if extracted is None:
        return result_factory(ClassifierStatus.SKIPPED, ClassifierReason.MISSING_MESSAGE, started_at, 0)

    message_text, message_chars = extracted

    env = os.environ if env is None else env
    base_url, api_key = _validate_classifier_env(env)

    if not base_url:
        result = result_factory(ClassifierStatus.ERROR, ClassifierReason.MISSING_BASE_URL, started_at, message_chars)
        if persist is not None:
            persist(result)
        return result
    if not api_key:
        result = result_factory(
            ClassifierStatus.ERROR, ClassifierReason.MISSING_API_KEY, started_at, message_chars, base_url=base_url
        )
        if persist is not None:
            persist(result)
        return result

    timeout_seconds = ctx.settings.last_assistant_message_classifier_timeout_seconds
    model = ctx.settings.classifier_model
    result = call_classifier_api(
        message_text,
        base_url,
        api_key,
        started_at,
        timeout_seconds,
        model,
        urlopen=urlopen,
    )
    if persist is not None:
        persist(result)
    return result
