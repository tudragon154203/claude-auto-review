import os
import time
from claude_auto_review.state.store_write import append_state, log_event
from claude_auto_review.stop.classifier.extraction import extract_last_assistant_message_text
from claude_auto_review.stop.classifier.models import (
    DEFAULT_TIMEOUT_SECONDS,
    result_factory
)
from claude_auto_review.stop.classifier.client import sanitize_base_url, call_classifier_api

def _persist_result(project_root, client_id, result):
    append_state(result.as_state_entry(include_debug=False), project_root, client_id=client_id)
    log_event(project_root, "last_assistant_message_classified", **result.as_state_entry(include_debug=True).to_dict())


def classify_last_assistant_message(project_root, client_id, payload, settings, env=None, urlopen=None):
    if not settings.get("lastAssistantMessageClassifierEnabled", True):
        return None

    started_at = time.monotonic()
    message_text = extract_last_assistant_message_text(payload)
    message_chars = len(message_text)
    env = os.environ if env is None else env

    if not message_text:
        result = result_factory("skipped", "missing_message", started_at, 0)
        _persist_result(project_root, client_id, result)
        return result

    base_url = sanitize_base_url(env.get("ANTHROPIC_BASE_URL", ""))
    api_key = env.get("ANTHROPIC_API_KEY", "")
    if not base_url:
        result = result_factory("error", "missing_base_url", started_at, message_chars)
        _persist_result(project_root, client_id, result)
        return result
    if not api_key:
        result = result_factory("error", "missing_api_key", started_at, message_chars, base_url=base_url)
        _persist_result(project_root, client_id, result)
        return result

    try:
        timeout_seconds = float(settings.get("lastAssistantMessageClassifierTimeoutSeconds", DEFAULT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout_seconds = float(DEFAULT_TIMEOUT_SECONDS)

    result = call_classifier_api(
        message_text,
        base_url,
        api_key,
        started_at,
        timeout_seconds,
        urlopen=urlopen
    )

    _persist_result(project_root, client_id, result)
    return result

