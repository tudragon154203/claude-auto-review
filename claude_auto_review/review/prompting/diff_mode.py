from __future__ import annotations

import difflib
import subprocess
from pathlib import Path

from claude_auto_review.runtime.client_dirs import client_snapshots_dir
from claude_auto_review.runtime.process import run_captured

_SNAPSHOT_SUFFIX = ".snap"


def snapshot_path_for(file_path: str, snapshots_dir: Path) -> Path:
    raw = str(file_path)
    if raw.startswith(("/", "\\")) or ".." in raw.replace("\\", "/").split("/"):
        raise ValueError("file_path must be a safe relative path")
    safe_name = raw.replace("/", "_").replace("\\", "_")
    return snapshots_dir / f"{safe_name}{_SNAPSHOT_SUFFIX}"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def capture_session_snapshot(file_path: str, project_root: Path, client_id: str) -> bool:
    snapshots_dir = client_snapshots_dir(project_root, client_id)
    snapshot_path = snapshot_path_for(file_path, snapshots_dir)
    if snapshot_path.exists():
        return True

    try:
        result = run_captured(["git", "show", f":{file_path}"], cwd=project_root, check=True)
    except (FileNotFoundError, OSError, subprocess.CalledProcessError):
        return False

    snapshot_path.write_text(result.stdout, encoding="utf-8", newline="\n")
    return True


def session_scoped_diff(file_path: str, project_root: Path, client_id: str) -> str:
    snapshot_path = snapshot_path_for(file_path, client_snapshots_dir(project_root, client_id))
    current_path = (Path(project_root) / file_path).resolve()

    if not snapshot_path.exists():
        if not current_path.exists():
            return "File does not currently exist."
        return _read_text(current_path)

    if not current_path.exists():
        current_text = ""
    else:
        current_text = _read_text(current_path)
    base_text = _read_text(snapshot_path)
    diff = difflib.unified_diff(
        base_text.splitlines(keepends=True),
        current_text.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    return "".join(diff)


def all_session_diffs(files: list[str], project_root: Path, client_id: str) -> str:
    sections: list[str] = []
    for file_path in files:
        sections.append(f"## {file_path}\n\n```diff\n{session_scoped_diff(file_path, project_root, client_id)}\n```")
    return "\n\n".join(sections)
