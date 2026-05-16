from claude_auto_review.stop.classifier.core.models import AssistantMessageClassificationResult


def classify_last_assistant_message(*args, **kwargs):
    from claude_auto_review.stop.classifier.core.last_assistant_message import classify_last_assistant_message as _impl

    return _impl(*args, **kwargs)

__all__ = [
    "AssistantMessageClassificationResult",
    "classify_last_assistant_message",
]
