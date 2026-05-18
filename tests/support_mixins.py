import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from claude_auto_review.runtime.client_dirs import client_run_dir

from tests.support_paths import REPO_ROOT


class TempProjectMixin:
    """Provides a temp_project(prefix) helper."""

    def temp_project(self, prefix="claude-auto-review-"):
        temp_dir = tempfile.TemporaryDirectory(prefix=prefix)
        if hasattr(self, "addCleanup"):
            self.addCleanup(temp_dir.cleanup)
        return Path(temp_dir.name)


class SubprocessMixin:
    """Provides a run_python helper for executing plugin claude_auto_review."""

    def run_python(
        self,
        script,
        project_root,
        input_text="",
        client_id="test-session",
        env_overrides=None,
        use_fake_claude=None,
        timeout=None,
        stdin_session_id_payload=None,
    ):
        env = {
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(project_root),
            "CLAUDE_SESSION_ID": client_id,
        }

        if use_fake_claude is None:
            use_fake_claude = str(script).replace("\\", "/").endswith("hooks/stop_hook.py")

        fake_dir = None
        if use_fake_claude:
            fake_dir = Path(tempfile.mkdtemp(prefix="claude-fake-"))
            fake_script = fake_dir / "claude_fake.py"
            fake_cmd = fake_dir / "claude.cmd"

            capture_file = client_run_dir(project_root, client_id) / "claude-cli-args.json"
            fake_script.write_text(
                "import json\n"
                "import os\n"
                "from pathlib import Path\n"
                "import sys\n\n"
                "capture = os.environ.get('CLAUDE_FAKE_CAPTURE_FILE')\n"
                "if capture:\n"
                "    path = Path(capture)\n"
                "    path.parent.mkdir(parents=True, exist_ok=True)\n"
                "    path.write_text(json.dumps(sys.argv[1:], indent=2), encoding='utf-8')\n"
                "print('# Review fake-claude')\n"
                "print()\n"
                "print('## Files Reviewed')\n"
                "print('- fake.ts (hash: deadbeef)')\n"
                "print()\n"
                "print('## Findings')\n"
                "print()\n"
                "print('Clean - no issues found. Claude may stop.')\n"
                "print()\n"
                "print('## Verdict')\n"
                "print()\n"
                "print('Clean - no issues found. Claude may stop.')\n",
                encoding="utf-8",
                newline="\n",
            )
            fake_cmd.write_text(
                f'@echo off\n"{sys.executable}" "%~dp0claude_fake.py" %*\n',
                encoding="utf-8",
                newline="\n",
            )
            env["PATH"] = str(fake_dir) + os.pathsep + env.get("PATH", "")
            env["CLAUDE_FAKE_CAPTURE_FILE"] = str(capture_file)

        if env_overrides:
            env.update(env_overrides)

        try:
            return subprocess.run(
                [sys.executable, str(REPO_ROOT / script)],
                cwd=project_root,
                input=input_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=timeout,
            )
        finally:
            if fake_dir is not None:
                shutil.rmtree(fake_dir, ignore_errors=True)
