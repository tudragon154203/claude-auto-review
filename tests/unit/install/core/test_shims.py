import tempfile
import unittest
from pathlib import Path

from claude_auto_review.install.core.shims import _write_text_if_changed, build_runpy_shim_content, write_project_script_shim


class TestShims(unittest.TestCase):
    def test_write_text_if_changed_writes_once_and_skips_unchanged_content(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="claude-auto-review-shims-"))
        target = temp_dir / "shim.py"

        _write_text_if_changed(target, "first")
        first_mtime = target.stat().st_mtime_ns
        _write_text_if_changed(target, "first")

        self.assertEqual(target.read_text(encoding="utf-8"), "first")
        self.assertEqual(target.stat().st_mtime_ns, first_mtime)

    def test_build_runpy_shim_content_targets_resolved_script(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="claude-auto-review-shims-"))
        script_path = temp_dir / "pkg" / "tool.py"
        script_path.parent.mkdir(parents=True, exist_ok=True)

        content = build_runpy_shim_content(script_path)

        expected = (
            "#!/usr/bin/env python3\n"
            "import runpy\n"
            "import sys\n"
            f"sys.path.insert(0, {str(script_path.parent.resolve())!r})\n"
            f"runpy.run_path({str(script_path.resolve())!r}, run_name='__main__')\n"
        )

        self.assertEqual(content, expected)

    def test_write_project_script_shim_writes_wrapper(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="claude-auto-review-shims-"))
        plugin_script = temp_dir / "plugin" / "script.py"
        plugin_script.parent.mkdir(parents=True, exist_ok=True)
        plugin_script.write_text("print('hello')\n", encoding="utf-8")
        shim_path = temp_dir / "runtime" / "script.py"

        write_project_script_shim(shim_path, plugin_script)

        content = shim_path.read_text(encoding="utf-8")
        self.assertEqual(content, build_runpy_shim_content(plugin_script))

    def test_write_project_script_shim_skips_when_paths_match(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="claude-auto-review-shims-"))
        script_path = temp_dir / "script.py"
        script_path.write_text("print('original')\n", encoding="utf-8")

        write_project_script_shim(script_path, script_path)

        self.assertEqual(script_path.read_text(encoding="utf-8"), "print('original')\n")
