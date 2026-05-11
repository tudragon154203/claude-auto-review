import json
import socket
from urllib import error, parse, request
from claude_auto_review.stop.models import (
    CLASSIFIER_MODEL,
    CLASSIFIER_MAX_TOKENS,
    _SYSTEM_PROMPT,
    result_factory
)

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

def call_classifier_api(message_text, base_url, api_key, started_at, timeout_seconds, urlopen=None):
    message_chars = len(message_text)
    urlopen = request.urlopen if urlopen is None else urlopen

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
            return result_factory(label, reason, started_at, message_chars, base_url=base_url)
    except error.HTTPError as exc:
        return result_factory("error", "http_error", started_at, message_chars, base_url=base_url, http_status=exc.code)
    except (socket.timeout, TimeoutError):
        return result_factory("error", "http_timeout", started_at, message_chars, base_url=base_url)
    except error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.timeout):
            return result_factory("error", "http_timeout", started_at, message_chars, base_url=base_url)
        else:
            return result_factory("error", "http_error", started_at, message_chars, base_url=base_url)
    except json.JSONDecodeError:
        return result_factory("error", "bad_response", started_at, message_chars, base_url=base_url)
    except Exception:
        return result_factory("error", "http_error", started_at, message_chars, base_url=base_url)
