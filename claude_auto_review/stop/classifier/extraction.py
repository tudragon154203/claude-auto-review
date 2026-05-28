from __future__ import annotations


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
