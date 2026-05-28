from __future__ import annotations

from claude_auto_review.stop.classifier.models import _SYSTEM_PROMPT, CLASSIFIER_MAX_TOKENS


def build_classifier_request_body(message_text, model):
    return {
        "model": model,
        "max_tokens": CLASSIFIER_MAX_TOKENS,
        "temperature": 0,
        "stop_sequences": ["\n"],
        "system": _SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Assistant message:\n{message_text}\n\nLabel:",
                    }
                ],
            }
        ],
    }
