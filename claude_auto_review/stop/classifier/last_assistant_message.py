import os
import time

from claude_auto_review.state.store.write import append_state_event
from claude_auto_review.stop.classifier.client import call_classifier_api, sanitize_base_url
from claude_auto_review.stop.classifier.extraction import extract_last_assistant_message_text
from claude_auto_review.stop.classifier.models import (
    DEFAULT_TIMEOUT_SECONDS,
    result_factory,
)
from claude_auto_review.stop.orchestration.context import RuntimeContext


def _persist_result(result, ctx):
    include_debug = ctx.settings.debug
    append_state_event(result.as_state_entry(include_debug=include_debug), ctx.project_root, client_id=ctx.client_id)


def classify_last_assistant_message(ctx: RuntimeContext, env=None, urlopen=None):
    if not ctx.settings.last_assistant_message_classifier_enabled:
        return None

    started_at = time.monotonic()
    message_text = extract_last_assistant_message_text(ctx.payload)
    message_chars = len(message_text)

    if not message_text:
        result = result_factory("skipped", "missing_message", started_at, 0)
        _persist_result(result, ctx)
        return result

    env = os.environ if env is None else env
    base_url = sanitize_base_url(env.get("ANTHROPIC_BASE_URL", ""))
    api_key = env.get("ANTHROPIC_API_KEY", "")

    if not base_url:
        result = result_factory("error", "missing_base_url", started_at, message_chars)
        _persist_result(result, ctx)
        return result
    if not api_key:
        result = result_factory("error", "missing_api_key", started_at, message_chars, base_url=base_url)
        _persist_result(result, ctx)
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
    _persist_result(result, ctx)
    return result
