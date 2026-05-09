"""Shared test support: temp-project and subprocess helpers."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TempProjectMixin:
    """Provides a temp_project(prefix) helper."""

    def temp_project(self, prefix="claude-auto-review-"):
        return Path(tempfile.mkdtemp(prefix=prefix))


class SubprocessMixin:
    """Provides a run_python helper for executing plugin scripts."""

    def run_python(self, script, project_root, input_text="", client_id="test-session"):
        env = {
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(project_root),
            "CLAUDE_SESSION_ID": client_id,
        }
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / script)],
            cwd=project_root,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
