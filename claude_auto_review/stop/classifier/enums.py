from __future__ import annotations

from enum import Enum


class ClassifierStatus(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNKNOWN = "unknown"
    ERROR = "error"
    SKIPPED = "skipped"


class ClassifierReason(str, Enum):
    PARSED_LABEL = "parsed_label"
    BAD_RESPONSE = "bad_response"
    INVALID_LABEL = "invalid_label"
    HTTP_ERROR = "http_error"
    HTTP_TIMEOUT = "http_timeout"
    MISSING_BASE_URL = "missing_base_url"
    MISSING_API_KEY = "missing_api_key"
    MISSING_MESSAGE = "missing_message"
