"""Parse raw JSONL dicts into StateEvent instances.

Uses the self-registering parser table from events.py so that adding
a new event type only requires editing the record module + events.py
registration — not this file.
"""

from __future__ import annotations

from typing import Any

from claude_auto_review.state.records.events import StateEvent, get_parser


def parse_event(raw: dict[str, Any]) -> StateEvent | None:
    if not isinstance(raw, dict):
        return None
    event_type: str | None = raw.get("type")
    parser = get_parser(event_type) if event_type is not None else None
    if parser is None:
        return None
    try:
        return parser(raw)
    except (TypeError, KeyError, ValueError):
        return None
