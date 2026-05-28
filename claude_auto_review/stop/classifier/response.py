from __future__ import annotations

import json
import re

from claude_auto_review.stop.classifier.enums import ClassifierReason, ClassifierStatus


def parse_classifier_label(response_json):
    if not isinstance(response_json, dict):
        return ClassifierStatus.UNKNOWN, ClassifierReason.BAD_RESPONSE
    content = response_json.get("content")
    if not isinstance(content, list):
        return ClassifierStatus.UNKNOWN, ClassifierReason.BAD_RESPONSE
    text = "".join(
        block.get("text", "")
        for block in content
        if (isinstance(block, dict) and block.get("type", "text") == "text" and isinstance(block.get("text"), str))
    )
    matches = re.findall(r"\b(complete|incomplete|unknown)\b", text.lower())
    if matches:
        return ClassifierStatus(matches[0]), ClassifierReason.PARSED_LABEL
    return ClassifierStatus.UNKNOWN, ClassifierReason.INVALID_LABEL


def response_payload_debug_json(response_data):
    return json.dumps(response_data, ensure_ascii=False, separators=(",", ":"))
