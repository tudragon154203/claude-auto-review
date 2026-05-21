from claude_auto_review.state.edit_record import EditRecord, StopBlockedRecord
from claude_auto_review.state.file_record import (
    ReviewFileRecord,
    _coerce_review_file_entries,
    _parse_review_file_entries,
    serialize_review_file_entries,
)
from claude_auto_review.state.review_records import (
    ReviewAutocompleteRecord,
    ReviewCompletedRecord,
    ReviewMetadata,
)
from claude_auto_review.state.classification_record import ClassificationRecord

# Union of all state event types for type annotations
StateEvent = (
    EditRecord
    | StopBlockedRecord
    | ReviewMetadata
    | ReviewCompletedRecord
    | ClassificationRecord
    | ReviewAutocompleteRecord
)
