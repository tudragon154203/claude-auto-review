from __future__ import annotations

import time
from dataclasses import dataclass

from claude_auto_review.config.constants import DEFAULT_CLASSIFIER_TIMEOUT_SECONDS, MS_PER_SECOND
from claude_auto_review.config.models import DEFAULT_CLASSIFIER_MODEL
from claude_auto_review.state.models import ClassificationRecord
from claude_auto_review.timestamps import local_now_iso

CLASSIFIER_MAX_TOKENS = 8
DEFAULT_TIMEOUT_SECONDS = DEFAULT_CLASSIFIER_TIMEOUT_SECONDS
CLASSIFICATION_EVENT = "last_assistant_message_classified"

_SYSTEM_PROMPT = (
    "You are a strict classifier. Classify whether the assistant message is a true "
    "completion or final answer. Return exactly one lowercase label: complete, "
    "incomplete, or unknown. Do not include punctuation, quotes, markdown, JSON, "
    "explanation, or any text other than the label."
)


@dataclass(frozen=True)
class AssistantMessageClassificationResult:
    status: str
    reason: str
    latency_ms: int
    message_chars: int
    model: str = DEFAULT_CLASSIFIER_MODEL
    base_url: str = ""
    http_status: int | None = None
    debug_response: str | None = None

    def as_state_entry(self, include_debug=False):
        return ClassificationRecord(
            timestamp=local_now_iso(),
            status=self.status,
            reason=self.reason,
            latencyMs=self.latency_ms,
            messageChars=self.message_chars,
            model=self.model,
            baseUrl=self.base_url,
            httpStatus=self.http_status,
            debugResponse=self.debug_response if include_debug else None,
        )


def result_factory(
    status,
    reason,
    started_at,
    message_chars,
    model=DEFAULT_CLASSIFIER_MODEL,
    base_url="",
    http_status=None,
    debug_response=None,
):
    return AssistantMessageClassificationResult(
        status=status,
        reason=reason,
        latency_ms=max(0, int((time.monotonic() - started_at) * MS_PER_SECOND)),
        message_chars=message_chars,
        model=model,
        base_url=base_url,
        http_status=http_status,
        debug_response=debug_response,
    )
