from __future__ import annotations

from collections.abc import Callable
from typing import Any

from claude_auto_review.state.models import (
    ClassificationRecord,
    EditRecord,
    ReviewAutocompleteRecord,
    ReviewCompletedRecord,
    ReviewMetadata,
    StateEvent,
    StopBlockedRecord,
)

_ParserFn = Callable[[dict[str, Any]], StateEvent]

_PARSERS: dict[str, _ParserFn] = {
    "edit": EditRecord.from_dict,
    "stop_blocked": StopBlockedRecord.from_dict,
    "review": ReviewMetadata.from_dict,
    "review_completed": ReviewCompletedRecord.from_dict,
    "last_assistant_message_classified": ClassificationRecord.from_dict,
    "review_autocomplete": ReviewAutocompleteRecord.from_dict,
}


def parse_event(raw: dict[str, Any]) -> StateEvent | None:
    if not isinstance(raw, dict):
        return None
    event_type: str | None = raw.get("type")
    parser = _PARSERS.get(event_type) if event_type is not None else None
    if parser is None:
        return None
    try:
        return parser(raw)
    except (TypeError, KeyError, ValueError):
        return None

