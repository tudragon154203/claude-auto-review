from __future__ import annotations

import json
import socket
from urllib import error, parse, request

from claude_auto_review.stop.classifier.enums import ClassifierReason, ClassifierStatus
from claude_auto_review.stop.classifier.models import result_factory
from claude_auto_review.stop.classifier.request import build_classifier_request_body
from claude_auto_review.stop.classifier.response import parse_classifier_label, response_payload_debug_json

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


def _build_classifier_request(message_text, api_key, model, base_url):
    body = json.dumps(build_classifier_request_body(message_text, model)).encode("utf-8")
    return request.Request(
        _request_url(base_url),
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
        },
        method="POST",
    )


def _error_result(status, reason, started_at, message_chars, *, model, base_url, http_status=None):
    return result_factory(
        status,
        reason,
        started_at,
        message_chars,
        model=model,
        base_url=base_url,
        http_status=http_status,
    )


def _request_classifier(req, timeout_seconds, urlopen):
    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            return response.read()
    except error.HTTPError as exc:
        raise RuntimeError((ClassifierReason.HTTP_ERROR, exc.code)) from exc
    except TimeoutError as exc:
        raise RuntimeError((ClassifierReason.HTTP_TIMEOUT, None)) from exc
    except error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.timeout):
            raise RuntimeError((ClassifierReason.HTTP_TIMEOUT, None)) from exc
        raise RuntimeError((ClassifierReason.HTTP_ERROR, None)) from exc
    except (OSError, RuntimeError) as exc:
        raise RuntimeError((ClassifierReason.HTTP_ERROR, None)) from exc


def _decode_response(response_bytes, started_at, message_chars, *, model, base_url):
    try:
        response_data = json.loads(response_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return _error_result(ClassifierStatus.ERROR, ClassifierReason.BAD_RESPONSE, started_at, message_chars, model=model, base_url=base_url)

    label, reason = parse_classifier_label(response_data)
    debug_response = response_payload_debug_json(response_data)
    return result_factory(label, reason, started_at, message_chars, model=model, base_url=base_url, debug_response=debug_response)


def call_classifier_api(message_text, base_url, api_key, started_at, timeout_seconds, model, urlopen=None):
    message_chars = len(message_text)
    urlopen = request.urlopen if urlopen is None else urlopen
    req = _build_classifier_request(message_text, api_key, model, base_url)

    try:
        response_bytes = _request_classifier(req, timeout_seconds, urlopen)
    except RuntimeError as exc:
        reason, http_status = exc.args[0]
        return _error_result(ClassifierStatus.ERROR, reason, started_at, message_chars, model=model, base_url=base_url, http_status=http_status)

    return _decode_response(response_bytes, started_at, message_chars, model=model, base_url=base_url)
