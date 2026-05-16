from claude_auto_review.state.store.parsing import parse_event
from claude_auto_review.state.store.read import read_jsonl_records


def prune_state_events(state_path, should_prune_event):
    raw_entries = read_jsonl_records(state_path)
    retained_lines = []
    removed = 0

    for line, raw in raw_entries:
        event = parse_event(raw) if isinstance(raw, dict) else None
        if event is not None and should_prune_event(event):
            removed += 1
            continue
        retained_lines.append(line)

    if removed > 0:
        with state_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(retained_lines) + "\n")
    return removed
