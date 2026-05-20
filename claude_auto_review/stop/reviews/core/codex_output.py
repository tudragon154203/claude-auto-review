import json


def _extract_codex_final_message(stdout):
    last_message = None
    for line in (stdout or "").splitlines():
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        event_type = event.get("type")
        msg = None
        if event_type == "turn.completed":
            msg = event.get("message") or event.get("output") or event.get("content")
        elif event_type == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                msg = item.get("text") or item.get("message") or item.get("content")
        if msg is None:
            continue
        if isinstance(msg, str) and msg.strip():
            last_message = msg.strip()
        elif isinstance(msg, dict):
            text = msg.get("text")
            if isinstance(text, str) and text.strip():
                last_message = text.strip()
        elif isinstance(msg, list):
            text_parts = []
            for item in msg:
                if isinstance(item, str) and item.strip():
                    text_parts.append(item.strip())
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        text_parts.append(text.strip())
            if text_parts:
                last_message = "\n".join(text_parts)
    return last_message or (stdout or "").strip()
