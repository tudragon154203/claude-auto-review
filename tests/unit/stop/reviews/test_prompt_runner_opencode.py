import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus
from claude_auto_review.stop.reviews.runners.dispatcher import (
    _register_default_backends,
    attempt_stop_autocomplete,
)
from claude_auto_review.stop.reviews.runners.opencode import (
    _SAFE_RE,
    _write_merged_prompt,
)
from claude_auto_review.stop.reviews.runners.args import _build_opencode_review_args
from tests.support_paths import FAKE_ROOT


def _ctx():
    return RuntimeContext(project_root=FAKE_ROOT, client_id="client-1")


class TestBuildOpencodeReviewArgs(unittest.TestCase):
    def test_returns_run_with_file_flag(self):
        prompt_file = Path("/tmp/prompt.md")
        args = _build_opencode_review_args("model", prompt_file)
        self.assertEqual(args[:3], ["run", "--pure", "Review the attached prompt file and respond with your findings."])
        self.assertIn("--file", args)
        file_idx = args.index("--file")
        self.assertEqual(args[file_idx + 1], str(prompt_file))

    def test_passes_model_argument_through(self):
        args = _build_opencode_review_args("my-model", Path("/tmp/prompt.md"))
        self.assertIn("--model", args)
        model_idx = args.index("--model")
        self.assertEqual(args[model_idx + 1], "my-model")
        self.assertIn("--file", args)
        self.assertLess(args.index("--model"), args.index("--file"))
        self.assertEqual(args[1], "--pure")

    def test_skips_model_when_default(self):
        args = _build_opencode_review_args("default", Path("/tmp/prompt.md"))
        self.assertNotIn("--model", args)

    def test_skips_model_when_none_string(self):
        args = _build_opencode_review_args("none", Path("/tmp/prompt.md"))
        self.assertNotIn("--model", args)

    def test_skips_model_when_empty(self):
        args = _build_opencode_review_args("", Path("/tmp/prompt.md"))
        self.assertNotIn("--model", args)

    def test_does_not_include_allowed_tools(self):
        args = _build_opencode_review_args("model", Path("/tmp/prompt.md"))
        self.assertNotIn("--allowedTools", args)
        self.assertNotIn("--sandbox", args)

    def test_prompt_not_in_cli_args(self):
        args = _build_opencode_review_args("model", Path("/tmp/prompt.md"))
        # The prompt should be in the file, not on the command line
        for arg in args:
            self.assertLessEqual(len(arg), 100, f"Arg too long for CLI: {arg[:60]}...")


class TestOpencodeBackendRegistration(unittest.TestCase):
    def test_opencode_registered_after_defaults(self):
        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()
        self.assertIn("opencode", _BACKEND_REGISTRY)


class TestOpencodeAutocomplete(unittest.TestCase):
    @patch("claude_auto_review.stop.reviews.runners.opencode.shutil.which", return_value=None)
    def test_cli_not_found(self, mock_which):
        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        result = _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-1", Path("/fake/review.md"), Path("/fake/prompt.md"),
            "user prompt", 60, "model",
        )
        self.assertEqual(result.status, AutocompleteStatus.CLI_NOT_FOUND)

    @patch("claude_auto_review.stop.reviews.runners.opencode.shutil.which", return_value="/usr/bin/opencode")
    def test_prompt_not_found(self, mock_which):
        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        result = _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-1", Path("/fake/review.md"), Path("/fake/nonexistent-prompt.md"),
            "user prompt", 60, "model",
        )
        self.assertEqual(result.status, AutocompleteStatus.PROMPT_NOT_FOUND)

    @patch(
        "claude_auto_review.stop.reviews.types.result.normalize_review_verdict_content",
        side_effect=lambda s, client_id=None, minimum_blocking_severity="medium": s,
    )
    @patch("claude_auto_review.stop.reviews.runners.cli.run_captured")
    @patch("claude_auto_review.stop.reviews.runners.opencode.shutil.which", return_value="/usr/bin/opencode")
    def test_output_written_on_success(self, mock_which, mock_run, _mock_norm):
        captured_merged = {}

        def _capture_run(*args, **kwargs):
            cmd_list = args[0]
            if "--file" in cmd_list:
                idx = cmd_list.index("--file")
                p = Path(cmd_list[idx + 1])
                if p.exists():
                    captured_merged["content"] = p.read_text(encoding="utf-8")
                    captured_merged["path"] = p
            return MagicMock(stdout="Clean - no issues found.", stderr="", returncode=0)

        mock_run.side_effect = _capture_run

        review_path = Path(tempfile.gettempdir()) / "review-opencode-ok.md"
        prompt_file = Path(tempfile.gettempdir()) / "prompt-opencode-ok.md"
        prompt_file.write_text("system prompt", encoding="utf-8")

        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        result = _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-ok", review_path, prompt_file,
            "user prompt", 60, "claude-sonnet-4-6",
        )

        self.assertEqual(result.status, AutocompleteStatus.OUTPUT_WRITTEN)
        self.assertEqual(review_path.read_text(encoding="utf-8"), "Clean - no issues found.")
        mock_which.assert_called_once_with("opencode")
        # Verify the merged prompt file contained both parts
        self.assertIn("system prompt", captured_merged["content"])
        self.assertIn("user prompt", captured_merged["content"])
        # Verify file is in the client run directory (prompt_file.parent), not system temp
        self.assertEqual(captured_merged["path"].parent, prompt_file.parent)

    @patch("claude_auto_review.stop.reviews.runners.cli.run_captured")
    @patch("claude_auto_review.stop.reviews.runners.opencode.shutil.which", return_value="/usr/bin/opencode")
    def test_nonzero_returncode(self, mock_which, mock_run):
        prompt_file = Path(tempfile.gettempdir()) / "prompt-opencode-nonzero.md"
        prompt_file.write_text("system", encoding="utf-8")
        mock_run.return_value = MagicMock(
            stdout="error output", stderr="some error", returncode=1,
        )

        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        result = _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-nz", Path("/fake/review.md"), prompt_file,
            "user prompt", 60, "model",
        )

        self.assertEqual(result.status, AutocompleteStatus.NONZERO)
        self.assertEqual(result.returncode, 1)

    @patch(
        "claude_auto_review.stop.reviews.runners.opencode.shutil.which",
        return_value="/usr/bin/opencode",
    )
    @patch(
        "claude_auto_review.stop.reviews.runners.cli.run_captured",
        side_effect=subprocess.TimeoutExpired(cmd="opencode", timeout=60),
    )
    def test_timeout(self, mock_run, mock_which):
        prompt_file = Path(tempfile.gettempdir()) / "prompt-opencode-timeout.md"
        prompt_file.write_text("system", encoding="utf-8")

        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        result = _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-to", Path("/fake/review.md"), prompt_file,
            "user prompt", 60, "model",
        )

        self.assertEqual(result.status, AutocompleteStatus.TIMEOUT)

    @patch(
        "claude_auto_review.stop.reviews.runners.opencode.shutil.which",
        return_value="/usr/bin/opencode",
    )
    @patch(
        "claude_auto_review.stop.reviews.runners.cli.run_captured",
        side_effect=OSError("permission denied"),
    )
    def test_os_error(self, mock_run, mock_which):
        prompt_file = Path(tempfile.gettempdir()) / "prompt-opencode-err.md"
        prompt_file.write_text("system", encoding="utf-8")

        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        result = _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-err", Path("/fake/review.md"), prompt_file,
            "user prompt", 60, "model",
        )

        self.assertEqual(result.status, AutocompleteStatus.ERROR)

    @patch("claude_auto_review.stop.reviews.runners.opencode.shutil.which", return_value="/usr/bin/opencode")
    def test_prompt_file_read_error(self, mock_which):
        prompt_file = MagicMock(spec=Path)
        prompt_file.is_file.return_value = True
        prompt_file.read_text.side_effect = PermissionError("access denied")

        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        result = _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-read-err", Path("/fake/review.md"), prompt_file,
            "user prompt", 60, "model",
        )

        self.assertEqual(result.status, AutocompleteStatus.ERROR)
        self.assertIn("access denied", result.stderr)

    @patch("claude_auto_review.stop.reviews.runners.cli.run_captured")
    @patch("claude_auto_review.stop.reviews.runners.opencode.shutil.which", return_value="/usr/bin/opencode")
    def test_empty_stdout(self, mock_which, mock_run):
        prompt_file = Path(tempfile.gettempdir()) / "prompt-opencode-empty.md"
        prompt_file.write_text("system", encoding="utf-8")
        mock_run.return_value = MagicMock(stdout="   ", stderr="", returncode=0)

        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        result = _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-empty", Path("/fake/review.md"), prompt_file,
            "user prompt", 60, "model",
        )

        self.assertEqual(result.status, AutocompleteStatus.EMPTY_STDOUT)

    @patch(
        "claude_auto_review.stop.reviews.types.result.normalize_review_verdict_content",
        side_effect=lambda s, client_id=None, minimum_blocking_severity="medium": s,
    )
    @patch("claude_auto_review.stop.reviews.runners.cli.run_captured")
    @patch("claude_auto_review.stop.reviews.runners.opencode.shutil.which", return_value="/usr/bin/opencode")
    def test_dispatch_via_attempt_stop_autocomplete(self, mock_which, mock_run, _mock_norm):
        review_path = Path(tempfile.gettempdir()) / "review-opencode-dispatch.md"
        prompt_file = Path(tempfile.gettempdir()) / "prompt-opencode-dispatch.md"
        prompt_file.write_text("system prompt", encoding="utf-8")
        mock_run.return_value = MagicMock(
            stdout="Clean - dispatched.", stderr="", returncode=0,
        )

        result = attempt_stop_autocomplete(
            _ctx(), "rev-dispatch", review_path, prompt_file,
            "user prompt", reviewer_timeout_seconds=60,
            model="claude-sonnet-4-6", backend="opencode",
        )

        self.assertEqual(result.status, AutocompleteStatus.OUTPUT_WRITTEN)
        mock_which.assert_called_once_with("opencode")


class TestWriteMergedPrompt(unittest.TestCase):
    def test_creates_file_with_content(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            path = _write_merged_prompt("hello world", tmp_dir, "rev-123")
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "hello world")
        finally:
            path.unlink(missing_ok=True)
            os.rmdir(tmp_dir)

    def test_sanitizes_review_id(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            path = _write_merged_prompt("content", tmp_dir, "rev-2026/05/31 evil")
            name = path.name
            self.assertNotIn("/", name)
            self.assertNotIn(" ", name)
            self.assertTrue(name.startswith("opencode-"))
            self.assertTrue(name.endswith("-merged-prompt.md"))
            content = path.read_text(encoding="utf-8")
            self.assertEqual(content, "content")
        finally:
            path.unlink(missing_ok=True)
            os.rmdir(tmp_dir)

    def test_file_is_in_run_dir(self):
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            path = _write_merged_prompt("x", tmp_dir, "rev-1")
            self.assertEqual(path.parent, tmp_dir)
        finally:
            path.unlink(missing_ok=True)
            os.rmdir(tmp_dir)

    def test_safe_re_regex(self):
        self.assertEqual(_SAFE_RE.sub("_", "rev-2026_05.31"), "rev-2026_05_31")
        self.assertEqual(_SAFE_RE.sub("_", "../../../etc/passwd"), "_________etc_passwd")


class TestEmptyPromptFallback(unittest.TestCase):
    @patch(
        "claude_auto_review.stop.reviews.types.result.normalize_review_verdict_content",
        side_effect=lambda s, client_id=None, minimum_blocking_severity="medium": s,
    )
    @patch("claude_auto_review.stop.reviews.runners.cli.run_captured")
    @patch("claude_auto_review.stop.reviews.runners.opencode.shutil.which", return_value="/usr/bin/opencode")
    def test_empty_prompt_file_uses_user_prompt_only(self, mock_which, mock_run, _mock_norm):
        captured_merged = {}

        def _capture_run(*args, **kwargs):
            cmd_list = args[0]
            if "--file" in cmd_list:
                idx = cmd_list.index("--file")
                p = Path(cmd_list[idx + 1])
                if p.exists():
                    captured_merged["content"] = p.read_text(encoding="utf-8")
            return MagicMock(stdout="Clean.", stderr="", returncode=0)

        mock_run.side_effect = _capture_run
        review_path = Path(tempfile.gettempdir()) / "review-opencode-empty-prompt.md"
        prompt_file = Path(tempfile.gettempdir()) / "prompt-opencode-empty-prompt.md"
        prompt_file.write_text("", encoding="utf-8")

        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        result = _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-ep", review_path, prompt_file,
            "standalone user prompt", 60, "model",
        )

        self.assertEqual(result.status, AutocompleteStatus.OUTPUT_WRITTEN)
        # When prompt file is empty, merged content should be just user_prompt
        self.assertEqual(captured_merged["content"], "standalone user prompt")
        self.assertNotIn("\n\n", captured_merged["content"])


class TestMergedFileCleanup(unittest.TestCase):
    @patch(
        "claude_auto_review.stop.reviews.types.result.normalize_review_verdict_content",
        side_effect=lambda s, client_id=None, minimum_blocking_severity="medium": s,
    )
    @patch("claude_auto_review.stop.reviews.runners.cli.run_captured")
    @patch("claude_auto_review.stop.reviews.runners.opencode.shutil.which", return_value="/usr/bin/opencode")
    def test_merged_file_cleaned_up_on_success(self, mock_which, mock_run, _mock_norm):
        merged_path_ref = [None]

        def _capture_run(*args, **kwargs):
            cmd_list = args[0]
            if "--file" in cmd_list:
                idx = cmd_list.index("--file")
                merged_path_ref[0] = Path(cmd_list[idx + 1])
            return MagicMock(stdout="Clean.", stderr="", returncode=0)

        mock_run.side_effect = _capture_run
        review_path = Path(tempfile.gettempdir()) / "review-opencode-cleanup.md"
        prompt_file = Path(tempfile.gettempdir()) / "prompt-opencode-cleanup.md"
        prompt_file.write_text("sys", encoding="utf-8")

        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-cl", review_path, prompt_file,
            "user", 60, "model",
        )

        self.assertFalse(merged_path_ref[0].exists(), "Merged file should be cleaned up after success")

    @patch("claude_auto_review.stop.reviews.runners.opencode.shutil.which", return_value="/usr/bin/opencode")
    @patch(
        "claude_auto_review.stop.reviews.runners.cli.run_captured",
        side_effect=subprocess.TimeoutExpired(cmd="opencode", timeout=60),
    )
    def test_merged_file_cleaned_up_on_timeout(self, mock_run, mock_which):
        prompt_file = Path(tempfile.gettempdir()) / "prompt-opencode-cleanup-to.md"
        prompt_file.write_text("sys", encoding="utf-8")

        from claude_auto_review.stop.reviews.runners.dispatcher import _BACKEND_REGISTRY

        _BACKEND_REGISTRY.clear()
        _register_default_backends()

        result = _BACKEND_REGISTRY["opencode"](
            _ctx(), "rev-cl-to", Path("/fake/review.md"), prompt_file,
            "user", 60, "model",
        )

        self.assertEqual(result.status, AutocompleteStatus.TIMEOUT)
        # The run dir should not have stale merged files
        run_dir = prompt_file.parent
        stale = list(run_dir.glob("opencode-*-merged-prompt.md"))
        self.assertEqual(len(stale), 0, "No stale merged files should remain after timeout")


if __name__ == "__main__":
    unittest.main()
