from __future__ import annotations

import os
import time
from typing import Callable

from claude_auto_review.stop.classifier.client import call_classifier_api, sanitize_base_url
from claude_auto_review.stop.classifier.enums import ClassifierReason, ClassifierStatus
from claude_auto_review.stop.classifier.extraction import extract_last_assistant_message_text
from claude_auto_review.stop.classifier.models import AssistantMessageClassificationResult, result_factory
from claude_auto_review.stop.orchestration.types.context import RuntimeContext


def _validate_classifier_env(env: dict) -> tuple[str, str]:
    base_url = sanitize_base_url(env.get("ANTHROPIC_BASE_URL", ""))
    api_key = env.get("ANTHROPIC_API_KEY", "")
    return base_url, api_key


def _extract_message_text(ctx: RuntimeContext) -> str | None:
    message_text = extract_last_assistant_message_text(ctx.payload)
    return message_text if message_text else None


def _validate_env_and_call_api(
    message_text: str,
    message_chars: int,
    env: dict,
    ctx: RuntimeContext,
    *,
    urlopen=None,
    started_at: float,
) -> AssistantMessageClassificationResult:
    base_url, api_key = _validate_classifier_env(env)

    if not base_url:
        return result_factory(ClassifierStatus.ERROR, ClassifierReason.MISSING_BASE_URL, started_at, message_chars)  # type: ignore[no-any-return]
    if not api_key:
        return result_factory(ClassifierStatus.ERROR, ClassifierReason.MISSING_API_KEY, started_at, message_chars, base_url=base_url)  # type: ignore[no-any-return]

    timeout_seconds = ctx.settings.last_assistant_message_classifier_timeout_seconds
    model = ctx.settings.classifier_model
    return call_classifier_api(  # type: ignore[no-any-return]
        message_text,
        base_url,
        api_key,
        started_at,
        timeout_seconds,
        model,
        urlopen=urlopen,
    )


def classify_last_assistant_message(
    ctx: RuntimeContext,
    env=None,
    urlopen=None,
    *,
    persist: Callable | None = None,
) -> AssistantMessageClassificationResult | None:
    if not ctx.settings.last_assistant_message_classifier_enabled:
        return None

    started_at = time.monotonic()

    message_text = _extract_message_text(ctx)
    if message_text is None:
        result = result_factory(ClassifierStatus.SKIPPED, ClassifierReason.MISSING_MESSAGE, started_at, 0)
        if persist is not None:
            persist(result)
        return result  # type: ignore[no-any-return]

    env = os.environ if env is None else env
    result = _validate_env_and_call_api(
        message_text, len(message_text), env, ctx, urlopen=urlopen, started_at=started_at
    )
    if persist is not None:
        persist(result)
    return result  # type: ignore[no-any-return]
