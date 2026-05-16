from claude_auto_review.state.store.read import read_jsonl_state_records


def _write_pruned_records(state_path, records, should_prune_event):
    retained_lines = []
    removed = 0

    for record in records:
        if record.event is not None and should_prune_event(record.event):
            removed += 1
            continue
        retained_lines.append(record.line)

    if removed > 0:
        with state_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(retained_lines) + "\n")
    return removed


def prune_state_records(state_path, records, should_prune_event):
    return _write_pruned_records(state_path, records, should_prune_event)


def prune_state_events(state_path, should_prune_event):
    return _write_pruned_records(state_path, read_jsonl_state_records(state_path), should_prune_event)
