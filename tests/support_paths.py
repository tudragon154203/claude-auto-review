import os
import shutil
from pathlib import Path

from claude_auto_review.runtime.client_dirs import get_client_runtime_dir


def client_dir(project_root, client_id="test-session"):
    return get_client_runtime_dir(Path(project_root), client_id)


def client_relpath(project_root, client_id="test-session"):
    return str(client_dir(project_root, client_id).relative_to(Path(project_root)))


REPO_ROOT = Path(__file__).resolve().parent.parent


def real_claude_cli_available():
    """Return True if CLAUDE_AUTO_REVIEW_TEST_REAL_CLI=1 and claude is on PATH."""
    if os.environ.get("CLAUDE_AUTO_REVIEW_TEST_REAL_CLI", "").strip() != "1":
        return False
    return shutil.which("claude") is not None


def real_codex_cli_available():
    """Return True if CLAUDE_AUTO_REVIEW_TEST_REAL_CODEX=1 and codex is on PATH."""
    if os.environ.get("CLAUDE_AUTO_REVIEW_TEST_REAL_CODEX", "").strip() != "1":
        return False
    return shutil.which("codex") is not None


def real_opencode_cli_available():
    """Return True if opencode is on PATH."""
    return shutil.which("opencode") is not None


def real_cli_available():
    """Backward-compatible alias for the real Claude CLI gate."""
    return real_claude_cli_available()
