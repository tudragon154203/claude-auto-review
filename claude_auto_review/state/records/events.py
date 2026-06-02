"""StateEvent union type and self-registering parser table.

Each concrete record class defines a _PARSER_KEY class attribute.
Importing this module triggers registration of all known event types
into the module-level _PARSER_REGISTRY, which parsing.py consumes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# --- Import concrete types ---

from claude_auto_review.state.records.classification import ClassificationRecord
from claude_auto_review.state.records.edit import EditRecord, StopBlockedRecord
from claude_auto_review.state.records.review import (
    ReviewAutocompleteRecord,
    ReviewCompletedRecord,
    ReviewMetadata,
)

# --- Union type ---

StateEvent = (
    EditRecord
    | StopBlockedRecord
    | ReviewMetadata
    | ReviewCompletedRecord
    | ClassificationRecord
    | ReviewAutocompleteRecord
)

# --- Public registry ---

_ParserFn = Callable[[dict[str, Any]], StateEvent]

_PARSER_REGISTRY: dict[str, _ParserFn] = {}


def register_event_type(key: str, parser_fn: _ParserFn) -> None:
    """Register a parser function for a state-event type discriminator."""
    _PARSER_REGISTRY[key] = parser_fn


def get_parser(key: str) -> _ParserFn | None:
    return _PARSER_REGISTRY.get(key)


def registered_event_types() -> list[str]:
    return list(_PARSER_REGISTRY.keys())


# Register each type's parser keyed by its discriminator
register_event_type("edit", EditRecord.from_dict)
register_event_type("stop_blocked", StopBlockedRecord.from_dict)
register_event_type("review", ReviewMetadata.from_dict)
register_event_type("review_completed", ReviewCompletedRecord.from_dict)
register_event_type("last_assistant_message_classified", ClassificationRecord.from_dict)
register_event_type("review_autocomplete", ReviewAutocompleteRecord.from_dict)
