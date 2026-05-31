from __future__ import annotations

from claude_auto_review.state.classification_record import ClassificationRecord
from claude_auto_review.state.edit_record import EditRecord, StopBlockedRecord
from claude_auto_review.state.review_records import (
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
