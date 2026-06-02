import os
import shutil
import tempfile
from pathlib import Path

from claude_auto_review.runtime.client_dirs import get_client_runtime_dir


def client_dir(project_root, client_id="test-session"):
    return get_client_runtime_dir(Path(project_root), client_id)


def client_relpath(project_root, client_id="test-session"):
    return str(client_dir(project_root, client_id).relative_to(Path(project_root)))


REPO_ROOT = Path(__file__).resolve().parent.parent

FAKE_ROOT = Path(tempfile.gettempdir()) / "claude-auto-review-fake"


def real_claude_cli_available():
    """Return True if _REAL_CLAUDE=1 and claude is on PATH."""
    if os.environ.get("_REAL_CLAUDE", "").strip() != "1":
        return False
    return shutil.which("claude") is not None


def real_codex_cli_available():
    """Return True if _REAL_CODEX=1 and codex is on PATH."""
    if os.environ.get("_REAL_CODEX", "").strip() != "1":
        return False
    return shutil.which("codex") is not None


def real_opencode_cli_available():
    """Return True if _REAL_OPENCODE=1 and opencode is on PATH."""
    if os.environ.get("_REAL_OPENCODE", "").strip() != "1":
        return False
    return shutil.which("opencode") is not None
