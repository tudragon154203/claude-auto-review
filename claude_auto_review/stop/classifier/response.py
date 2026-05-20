import json
import re


def parse_classifier_label(response_json):
    if not isinstance(response_json, dict):
        return "unknown", "bad_response"
    content = response_json.get("content")
    if not isinstance(content, list):
        return "unknown", "bad_response"
    text = "".join(
        block.get("text", "")
        for block in content
        if (
            isinstance(block, dict)
            and block.get("type", "text") == "text"
            and isinstance(block.get("text"), str)
        )
    )
    matches = re.findall(r"\b(complete|incomplete|unknown)\b", text.lower())
    if matches:
        return matches[0], "parsed_label"
    return "unknown", "invalid_label"


def response_payload_debug_json(response_data):
    return json.dumps(response_data, ensure_ascii=False, separators=(",", ":"))
