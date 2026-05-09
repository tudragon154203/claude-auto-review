import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class HookTestCase:
    """Shared base for hook integration tests."""

    def temp_project(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-hooks-"))
        (project_root / "src").mkdir(parents=True)
        return project_root

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

    def complete_latest_review(self, project_root, verdict="Clean - no issues found. Claude may stop."):
        review_path = sorted((project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        content = content.replace("Pending. Claude must complete this review from", "Completed review from")
        content = content.replace("Pending.", verdict)
        review_path.write_text(content, encoding="utf-8", newline="\n")
        return review_path
