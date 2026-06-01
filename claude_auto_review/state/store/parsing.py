from __future__ import annotations

from collections.abc import Callable
from typing import Any

from claude_auto_review.state.classification_record import ClassificationRecord
from claude_auto_review.state.edit_record import EditRecord, StopBlockedRecord
from claude_auto_review.state.review_records import (
    ReviewAutocompleteRecord,
    ReviewCompletedRecord,
    ReviewMetadata,
)
from claude_auto_review.state.event_types import StateEvent

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

