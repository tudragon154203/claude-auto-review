import json
import socket
from urllib import error, parse, request
from claude_auto_review.stop.classifier.models import result_factory
from claude_auto_review.stop.classifier.request import build_classifier_request_body
from claude_auto_review.stop.classifier.response import parse_classifier_label, response_payload_debug_json

_parse_classifier_label = parse_classifier_label

ANTHROPIC_API_VERSION = "2023-06-01"

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


def call_classifier_api(message_text, base_url, api_key, started_at, timeout_seconds, urlopen=None):
    message_chars = len(message_text)
    urlopen = request.urlopen if urlopen is None else urlopen

    body = json.dumps(build_classifier_request_body(message_text)).encode("utf-8")
    req = request.Request(
        _request_url(base_url),
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            response_bytes = response.read()
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
    except (OSError, RuntimeError):
        return result_factory("error", "http_error", started_at, message_chars, base_url=base_url)

    try:
        response_data = json.loads(response_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return result_factory("error", "bad_response", started_at, message_chars, base_url=base_url)

    label, reason = parse_classifier_label(response_data)
    debug_response = None
    if label == "unknown":
        debug_response = response_payload_debug_json(response_data)
    return result_factory(label, reason, started_at, message_chars, base_url=base_url, debug_response=debug_response)

