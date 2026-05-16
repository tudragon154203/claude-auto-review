from dataclasses import dataclass
from typing import Any

from claude_auto_review.state.models import StateEvent
from claude_auto_review.state.store.parsing import parse_event


@dataclass(frozen=True)
class JsonlStateRecord:
    line: str
    raw: Any
    event: StateEvent | None


def parse_jsonl_state_records(raw_entries) -> list[JsonlStateRecord]:
    records = []
    for line, raw in raw_entries:
        event = parse_event(raw) if isinstance(raw, dict) else None
        records.append(JsonlStateRecord(line=line, raw=raw, event=event))
    return records
