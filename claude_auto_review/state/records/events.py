from __future__ import annotations

from claude_auto_review.state.records.classification import ClassificationRecord
from claude_auto_review.state.records.edit import EditRecord, StopBlockedRecord
from claude_auto_review.state.records.review import (
    ReviewAutocompleteRecord,
    ReviewCompletedRecord,
    ReviewMetadata,
)

StateEvent = (
    EditRecord
    | StopBlockedRecord
    | ReviewMetadata
    | ReviewCompletedRecord
    | ClassificationRecord
    | ReviewAutocompleteRecord
)
