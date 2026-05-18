import unittest
from pathlib import Path
from unittest.mock import patch


class TestProcess(unittest.TestCase):

    def test_run_fail_open_logs_handler_failure_before_fallback(self):
        from claude_auto_review.runtime.process import run_fail_open

        def callback():
            raise ValueError("boom")

        def on_error(error):
            raise RuntimeError("handler boom")

        with patch("claude_auto_review.runtime.events.log_failure") as mock_log:
            result = run_fail_open(
                callback,
                project_root=Path("/fake"),
                event_type="test_event",
                on_error=on_error,
                fallback=7,
            )

        self.assertEqual(result, 7)
        self.assertEqual(mock_log.call_count, 2)
        self.assertEqual(mock_log.call_args_list[0].args[1], "test_event_handler_failed")
        self.assertEqual(mock_log.call_args_list[1].args[1], "test_event")

    def test_run_fail_open_treats_truthy_handler_as_handled(self):
        from claude_auto_review.runtime.process import run_fail_open

        def callback():
            raise ValueError("boom")

        def on_error(error):
            return True

        with patch("claude_auto_review.runtime.events.log_failure") as mock_log:
            result = run_fail_open(
                callback,
                project_root=Path("/fake"),
                event_type="test_event",
                on_error=on_error,
                fallback=7,
            )

        self.assertEqual(result, 7)
        mock_log.assert_not_called()

    def test_helpers_log_event_oserror_suppression(self):
        from claude_auto_review.runtime.events import log_event
        with patch("claude_auto_review.runtime.events.write_jsonl_line", side_effect=OSError("no write")):
            self.assertFalse(log_event(Path("/fake"), "test_event"))

    def test_helpers_log_failure_propagates_log_failure(self):
        from claude_auto_review.runtime.events import log_failure
        with patch("claude_auto_review.runtime.events.write_jsonl_line", side_effect=OSError("no write")):
            self.assertFalse(log_failure(Path("/fake"), "test_event", ValueError("boom")))

    def test_append_state_uses_shared_jsonl_append(self):
        from claude_auto_review.state.models import EditRecord
        from claude_auto_review.state.store.write import append_state_event

        with patch("claude_auto_review.state.store.write.ensure_client_runtime"), patch(
            "claude_auto_review.state.store.write.write_jsonl_line"
        ) as mock_append:
            append_state_event(
                EditRecord(
                    timestamp="2026-05-05T08:00:00+07:00",
                    file="src/app.ts",
                    hash="abc123",
                ),
                Path("/fake/project"),
                client_id="session-1",
            )

        mock_append.assert_called_once()
        path_arg, entry_arg = mock_append.call_args.args
        self.assertTrue(str(path_arg).endswith("state.jsonl"))
        self.assertEqual(entry_arg["type"], "edit")
        self.assertEqual(entry_arg["file"], "src/app.ts")

