from pathlib import Path

from claude_auto_review.utils.core.datetime_utils import parse_iso_timestamp


_TEXT_READ_CHUNK_SIZE = 8192
_SNAPSHOT_READ_LIMIT_CHARS = 10000
_SNAPSHOT_RENDER_LIMIT_CHARS = 40000


def _read_text_with_limit(path, max_chars, encoding="utf-8"):
    chunks = []
    remaining = max_chars
    with Path(path).open("r", encoding=encoding, errors="replace") as handle:
        while remaining > 0:
            chunk = handle.read(min(remaining, _TEXT_READ_CHUNK_SIZE))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    return "".join(chunks)


def format_review_timestamp(timestamp):
    ts = parse_iso_timestamp(timestamp)
    local_ts = ts.astimezone()
    offset = local_ts.strftime("%z")
    offset = f"{offset[:3]}:{offset[3:]}" if offset else ""
    return f"{local_ts.strftime('%Y-%m-%d | %H:%M:%S')} {offset}".rstrip()


def format_file_list(entries):
    return "\n".join(f"- {entry.file} (hash: {entry.hash})" for entry in entries)


def _review_context(entries, timestamp):
    return format_review_timestamp(timestamp), format_file_list(entries)


def current_file_snapshots(files, project_root):
    sections = []
    for file_path in files:
        sections.append(_snapshot_section(file_path, project_root, _SNAPSHOT_READ_LIMIT_CHARS))
    return "\n\n".join(sections)


def _snapshot_section(file_path, project_root, max_chars):
    full_path = (Path(project_root) / file_path).resolve()
    if not full_path.is_relative_to(Path(project_root).resolve()):
        return _format_missing_file_snapshot(file_path)
    if not full_path.is_file():
        return _format_missing_file_snapshot(file_path)
    # Read max_chars + 1 so _format_file_snapshot can detect if truncation occurred
    content = _read_text_with_limit(full_path, max_chars + 1)
    return _format_file_snapshot(file_path, content, max_chars=max_chars)


def _format_missing_file_snapshot(file_path):
    return f"## {file_path}\n\nFile does not currently exist."


def _format_file_snapshot(file_path, content, max_chars=_SNAPSHOT_RENDER_LIMIT_CHARS):
    if len(content) > max_chars:
        content = f"{content[:max_chars]}\n\n[truncated at {max_chars} characters]"
    return f"## {file_path}\n\n```\n{content}\n```"
