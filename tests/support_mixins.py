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

    @staticmethod
    def _write_fake_claude_cli(fake_dir, capture_file):
        fake_script = fake_dir / "claude"
        fake_script.write_text(
            "#!/usr/bin/env python3\n"
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
        fake_cmd = fake_dir / "claude.cmd"
        fake_cmd.write_text(
            f'@echo off\n"{sys.executable}" "%~dp0claude" %*\n',
            encoding="utf-8",
            newline="\n",
        )
        fake_script.chmod(0o755)

    @staticmethod
    def _write_fake_codex_cli(fake_dir, capture_file, stdin_file):
        fake_script = fake_dir / "codex"
        fake_script.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import os\n"
            "from pathlib import Path\n"
            "import sys\n\n"
            "capture = os.environ.get('CODEX_FAKE_CAPTURE_FILE')\n"
            "if capture:\n"
            "    path = Path(capture)\n"
            "    path.parent.mkdir(parents=True, exist_ok=True)\n"
            "    path.write_text(json.dumps(sys.argv[1:], indent=2), encoding='utf-8')\n"
            "stdin_text = sys.stdin.read()\n"
            "stdin_capture = os.environ.get('CODEX_FAKE_STDIN_FILE')\n"
            "if stdin_capture:\n"
            "    path = Path(stdin_capture)\n"
            "    path.parent.mkdir(parents=True, exist_ok=True)\n"
            "    path.write_text(stdin_text, encoding='utf-8')\n"
            "mode = os.environ.get('CODEX_FAKE_MODE', 'success')\n"
            "review = '''# Review fake-codex\n\n## Files Reviewed\n- fake.ts (hash: deadbeef)\n\n## Findings\n\nClean - no issues found. Claude may stop.\n\n## Verdict\n\nClean - no issues found. Claude may stop.\n'''\n"
            "args = sys.argv[1:]\n"
            "if mode == 'empty':\n"
            "    sys.exit(0)\n"
            "if '--output-last-message' in args:\n"
            "    idx = args.index('--output-last-message')\n"
            "    Path(args[idx + 1]).write_text(review, encoding='utf-8')\n"
            "print(json.dumps({'type': 'turn.completed', 'message': {'text': review}}))\n",
            encoding="utf-8",
            newline="\n",
        )
        fake_cmd = fake_dir / "codex.cmd"
        fake_cmd.write_text(
            f'@echo off\n"{sys.executable}" "%~dp0codex" %*\n',
            encoding="utf-8",
            newline="\n",
        )
        fake_script.chmod(0o755)

    def run_python(
        self,
        script,
        project_root,
        input_text="",
        client_id="test-session",
        env_overrides=None,
        use_fake_claude=None,
        use_fake_codex=False,
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
        if use_fake_claude or use_fake_codex:
            fake_dir = Path(tempfile.mkdtemp(prefix="claude-fake-"))
            env["PATH"] = str(fake_dir) + os.pathsep + env.get("PATH", "")
            run_dir = client_run_dir(project_root, client_id)
            if use_fake_claude:
                capture_file = run_dir / "claude-cli-args.json"
                self._write_fake_claude_cli(fake_dir, capture_file)
                env["CLAUDE_FAKE_CAPTURE_FILE"] = str(capture_file)
            if use_fake_codex:
                capture_file = run_dir / "codex-cli-args.json"
                stdin_file = run_dir / "codex-cli-stdin.txt"
                self._write_fake_codex_cli(fake_dir, capture_file, stdin_file)
                env["CODEX_FAKE_CAPTURE_FILE"] = str(capture_file)
                env["CODEX_FAKE_STDIN_FILE"] = str(stdin_file)

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
