import json
from typing import Optional


def _extract_codex_final_message(stdout: Optional[str]) -> str:
    messages = []
    for line in (stdout or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            # Not valid JSON - preserve the line (including empty lines for formatting)
            messages.append(line)
            continue

        # Non-dict JSON (lists, strings, numbers) - preserve original line as user content
        if not isinstance(event, dict):
            messages.append(line)
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
            # JSON line but no recognized message - skip (control events like
            # turn.started have no useful content)
            continue

        # Skip whitespace-only content from JSON (noise/errors), preserve non-empty
        if isinstance(msg, str) and msg.strip():
            messages.append(msg)
        elif isinstance(msg, dict):
            text = msg.get("text")
            if isinstance(text, str) and text.strip():
                messages.append(text)
        elif isinstance(msg, list):
            for item in msg:
                if isinstance(item, str) and item.strip():
                    messages.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        messages.append(text)

    if messages:
        content = "\n".join(messages)
        idx = content.rfind("# Review rev-")
        if idx >= 0:
            return content[idx:]
        return content
    return stdout or ""
