from claude_auto_review.stop.classifier.models import CLASSIFIER_MAX_TOKENS, CLASSIFIER_MODEL, _SYSTEM_PROMPT


def build_classifier_request_body(message_text):
    return {
        "model": CLASSIFIER_MODEL,
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
