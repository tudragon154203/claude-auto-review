import time
from dataclasses import asdict, dataclass
from claude_auto_review.paths import local_now_iso

CLASSIFIER_MODEL = "claude-3-5-haiku-20241022"
CLASSIFIER_MAX_TOKENS = 16
DEFAULT_TIMEOUT_SECONDS = 10
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
    model: str = CLASSIFIER_MODEL
    base_url: str = ""
    http_status: int | None = None
    debug_response: str | None = None

    def as_event_fields(self):
        fields = asdict(self)
        if fields["http_status"] is None:
            fields.pop("http_status")
        if fields["debug_response"] is None:
            fields.pop("debug_response")
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

def result_factory(status, reason, started_at, message_chars, base_url="", http_status=None, debug_response=None):
    return AssistantMessageClassificationResult(
        status=status,
        reason=reason,
        latency_ms=max(0, int((time.monotonic() - started_at) * 1000)),
        message_chars=message_chars,
        base_url=base_url,
        http_status=http_status,
        debug_response=debug_response,
    )
