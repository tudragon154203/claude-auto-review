# Plan: Unify log and state.jsonl event schemas

## Problem

Two separate event systems with divergent schemas:
- `log_event()` → `claude-auto-review.log` using `{"event": "name", **kwargs}`
- `append_state()` → `clients/{id}/state.jsonl` using `{"type": "name", ...}`

Event names and fields drift between them. Adding/changing events requires editing multiple places.

## Goal

Define all events in ONE place (canonical schema), and have both log and state.jsonl use that schema. State.jsonl format is the reference.

## Phase 1: Define unified event dataclasses in `state/models.py`

Add dataclasses for every event type the system writes. Format matches what currently goes to state.jsonl (since that's the reference):

```python
# Existing: StateEntry, EditRecord, StopBlockedRecord, ReviewMetadata
# Add these new ones:

@dataclass
class ReviewCompletedRecord(StateEntry):
    type: Literal["review_completed"] = "review_completed"
    reviewId: str
    files: list[dict[str, str]]
    clientId: str
    duration: Optional[str] = None
    durationSeconds: Optional[float] = None
```

Also add helper functions:
- `make_edit_event(file, hash, reviewed, deleted, reviewId, timestamp)` → dict
- `make_stop_blocked_event(reason, reviewId, files, timestamp)` → dict
- `make_review_event(...)` → dict
- `make_review_completed_event(...)` → dict
- `make_classification_event(...)` → dict
- `make_log_event(event_type, **kwargs)` → dict (for log-only events)

These factory functions produce dicts in the SAME canonical format that state.jsonl uses. BOTH `log_event()` and `append_state()` call these factories.

## Phase 2: Update write path to use canonical events

### `runtime/helpers.py` - `log_event()`

Change to use the canonical event format (state.jsonl style) for log writing:
```python
def log_event(project_root, event_type, **kwargs):
    entry = {"timestamp": local_now_iso(), "type": event_type, **kwargs}
    # Write to .log file
    ...
```
Key change: `"event": event_type` → `"type": event_type` (matches state.jsonl format).

### `state/store_write.py` - `append_state()` / helper functions

Replace dict literals with factory function calls from `models.py`. Eg:
```python
def _review_state_entry(entries, review_id, review_path, client_id):
    return make_review_event(entries, review_id, review_path, client_id)
```

No longer define event structure in multiple places — always go through factories.

## Phase 3: Eliminate dual log_event + append_state calls

Currently several callers call BOTH `log_event()` and `append_state()` for the same event (e.g., `stop/feedback.py`, `completion.py`). After this change:

- If an event belongs in state.jsonl → call `append_state()` only (it's also the "log" for that event)
- If an event is operational-only → call `log_event()` only
- No more parallel calls for the same data

But events that currently call BOTH will be collapsed: remove the `log_event()` call and keep `append_state()`. Since log and state now write the same format, you can grep the .log file the same way.

### Specific changes:

**`stop/feedback.py`** - `block_completed_review_findings()`:
- Remove `log_event("stop_blocked", ...)` call
- Keep `append_state({"type": "stop_blocked", ...})` call

**`review/completion.py`** - `apply_completed_review()`:
- Remove `log_event("stop_approved", ...)` call  
- Remove `log_event("stop_blocked_after_partial_review", ...)` call
- Keep the `append_state()` calls

**`stop/orchestration/finalize.py`** - `finalize_review_stop()`:
- Remove `log_event("stop_blocked", ...)` call (keep `append_state()`)

**`stop/classifier/last_assistant_message.py`** - `_persist_result()`:
- Remove `log_event(CLASSIFICATION_EVENT, ...)` call
- Keep `append_state(result.as_state_entry())`

## Phase 4: One-off operational logs stay as pure log_event

Events that have no state.jsonl counterpart remain as `log_event()` calls only:
- `stop_approved`, `stop_disabled` (flow decision logs)
- `post_tool_use_disabled`, `post_tool_use_ignored_path`, `post_tool_use_skipped_file`, `post_tool_use_error` (debug logs)
- `file_tracked`, `file_deletion_tracked` (redundant with state.jsonl "edit" entries — keep for now)
- `stop_hook_*` (CLI/subprocess logs)
- `review_prompt_*`
- `setup_completed`, `cancel_completed`
- `session_end_*`
- `expired_reviews_cleaned`

These all use the new canonical format (type: instead of event:).

## Phase 5: Update tests

- Update test assertions that check log file format (event: → type:)
- Update test assertions that check state.jsonl format (should be identical)
- Verify no test fails due to removed log_event calls

## Files to modify

| File | Change |
|------|--------|
| `state/models.py` | Add new event dataclasses + factory functions |
| `runtime/helpers.py` | Change log format to use `type:` instead of `event:` |
| `state/store_write.py` | Route through factory functions |
| `stop/feedback.py` | Remove redundant log_event |
| `review/completion.py` | Remove redundant log_event calls |
| `stop/orchestration/finalize.py` | Remove redundant log_event |
| `stop/classifier/last_assistant_message.py` | Remove redundant log_event |
| Tests (various) | Update format assertions |

## Non-goals (out of scope)

- No migration of historical state.jsonl files
- No renaming existing field names (backward compat)
- No new pydantic/validation dependencies
- No schema version header
- No change to the reading/consumption path (state/store_read.py stays as-is)
