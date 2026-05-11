import json
import os
import socket
import time
from dataclasses import asdict, dataclass
from urllib import error, parse, request

from claude_auto_review.paths import local_now_iso
from claude_auto_review.runtime.helpers import log_event
from claude_auto_review.state.store_write import append_state

CLASSIFIER_MODEL = "claude-3-5-haiku-20241022"
CLASSIFIER_MAX_TOKENS = 16
DEFAULT_TIMEOUT_SECONDS = 10
CLASSIFICATION_EVENT = "last_assistant_message_classified"

_SYSTEM_PROMPT = (
    "Classify whether the assistant message is a true completion or final answer. "
    "Output exactly one label only: complete, incomplete, or unknown."
)


@dataclass(frozen=True)
class AssistantMessageClassificationResult:
    status: str
    reason: str
    latency_ms: int
    message_chars: int
    model: str = CLASSIFIER_MODEL
    base_url: str = ""
    http_status: int | None = None

    def as_event_fields(self):
        fields = asdict(self)
        if fields["http_status"] is None:
            fields.pop("http_status")
        return fields

    def as_state_entry(self):
        entry = {
            "type": "assistant_message_classification",
            "timestamp": local_now_iso(),
            "status": self.status,
            "reason": self.reason,
            "latencyMs": self.latency_ms,
            "messageChars": self.message_chars,
            "model": self.model,
            "baseUrl": self.base_url,
        }
        if self.http_status is not None:
            entry["httpStatus"] = self.http_status
        return entry


def _extract_message_candidate(payload):
    if not isinstance(payload, dict):
        return None
    if "last_assistant_message" in payload:
        return payload.get("last_assistant_message")
    if "lastAssistantMessage" in payload:
        return payload.get("lastAssistantMessage")
    conversation = payload.get("conversation")
    if isinstance(conversation, dict):
        return conversation.get("last_assistant_message")
    return None


def _normalize_message_content(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""

    content = value.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def extract_last_assistant_message_text(payload):
    return _normalize_message_content(_extract_message_candidate(payload)).strip()


def sanitize_base_url(base_url):
    if not isinstance(base_url, str) or not base_url.strip():
        return ""
    try:
        parts = parse.urlsplit(base_url.strip())
    except ValueError:
        return ""
    netloc = parts.netloc.rsplit("@", 1)[-1]
    path = parts.path.rstrip("/")
    return parse.urlunsplit((parts.scheme, netloc, path, "", ""))


def _request_url(base_url):
    sanitized = sanitize_base_url(base_url)
    if not sanitized:
        return ""
    return f"{sanitized}/v1/messages"


def _build_request_body(message_text):
    return {
        "model": CLASSIFIER_MODEL,
        "max_tokens": CLASSIFIER_MAX_TOKENS,
        "temperature": 0,
        "system": _SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Assistant message:\n{message_text}",
                    }
                ],
            }
        ],
    }


def _parse_classifier_label(response_json):
    content = response_json.get("content")
    if not isinstance(content, list):
        return "unknown", "bad_response"
    text = "".join(block.get("text", "") for block in content if isinstance(block, dict) and isinstance(block.get("text"), str))
    label = text.strip().lower()
    if label in {"complete", "incomplete", "unknown"}:
        return label, "parsed_label"
    return "unknown", "invalid_label"


def _result(status, reason, started_at, message_chars, base_url="", http_status=None):
    return AssistantMessageClassificationResult(
        status=status,
        reason=reason,
        latency_ms=max(0, int((time.monotonic() - started_at) * 1000)),
        message_chars=message_chars,
        base_url=base_url,
        http_status=http_status,
    )


def _persist_result(project_root, client_id, result):
    log_event(project_root, CLASSIFICATION_EVENT, **result.as_event_fields())
    append_state(result.as_state_entry(), project_root, client_id=client_id)


def classify_last_assistant_message(project_root, client_id, payload, settings, env=None, urlopen=None):
    if not settings.get("lastAssistantMessageClassifierEnabled", True):
        return None

    started_at = time.monotonic()
    message_text = extract_last_assistant_message_text(payload)
    message_chars = len(message_text)
    env = os.environ if env is None else env
    urlopen = request.urlopen if urlopen is None else urlopen

    if not message_text:
        result = _result("skipped", "missing_message", started_at, 0)
        _persist_result(project_root, client_id, result)
        return result

    base_url = sanitize_base_url(env.get("ANTHROPIC_BASE_URL", ""))
    api_key = env.get("ANTHROPIC_API_KEY", "")
    if not base_url:
        result = _result("error", "missing_base_url", started_at, message_chars)
        _persist_result(project_root, client_id, result)
        return result
    if not api_key:
        result = _result("error", "missing_api_key", started_at, message_chars, base_url=base_url)
        _persist_result(project_root, client_id, result)
        return result

    try:
        timeout_seconds = float(settings.get("lastAssistantMessageClassifierTimeoutSeconds", DEFAULT_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout_seconds = float(DEFAULT_TIMEOUT_SECONDS)
    body = json.dumps(_build_request_body(message_text)).encode("utf-8")
    req = request.Request(
        _request_url(base_url),
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            response_data = json.loads(response.read().decode("utf-8"))
            label, reason = _parse_classifier_label(response_data)
            result = _result(label, reason, started_at, message_chars, base_url=base_url)
    except error.HTTPError as exc:
        result = _result("error", "http_error", started_at, message_chars, base_url=base_url, http_status=exc.code)
    except (socket.timeout, TimeoutError):
        result = _result("error", "http_timeout", started_at, message_chars, base_url=base_url)
    except error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.timeout):
            result = _result("error", "http_timeout", started_at, message_chars, base_url=base_url)
        else:
            result = _result("error", "http_error", started_at, message_chars, base_url=base_url)
    except json.JSONDecodeError:
        result = _result("error", "bad_response", started_at, message_chars, base_url=base_url)
    except Exception:
        result = _result("error", "http_error", started_at, message_chars, base_url=base_url)

    _persist_result(project_root, client_id, result)
    return result
