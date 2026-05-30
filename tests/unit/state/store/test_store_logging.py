import unittest

from claude_auto_review.paths.path_utils import get_state_path, local_now_iso
from claude_auto_review.runtime.client_dirs import client_state_path
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.setup import ensure_client_runtime
from tests.unit.state.support import StateTestCase


class TestStateStoreLogging(StateTestCase, unittest.TestCase):
    def test_local_now_iso_returns_valid_iso_format(self):
        result = local_now_iso()
        self.assertFalse(result.endswith("Z"))
        self.assertIn("T", result)

    def test_local_now_iso_returns_system_timezone_format(self):
        result = local_now_iso()
        self.assertIn("T", result)
        self.assertNotIn("Z", result)
        self.assertRegex(result, r"[+-]\d{2}:\d{2}$")

    def test_log_event_creates_log_file(self):
        project_root = self.temp_project()
        log_event(project_root, "test_event", extra="data")
        log_path = get_state_path(project_root)
        self.assertTrue(log_path.exists())
        content = log_path.read_text(encoding="utf-8")
        self.assertIn('"type":"test_event"', content)

    def test_log_event_appends_to_existing_log(self):
        project_root = self.temp_project()
        log_event(project_root, "first")
        log_event(project_root, "second")
        log_path = get_state_path(project_root)
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)

    def test_log_event_with_client_writes_to_both_logs(self):
        project_root = self.temp_project()
        client_id = "test-dual-write"
        ensure_client_runtime(project_root, client_id)
        log_event(project_root, "file_tracked", client_id=client_id, file="a.ts")
        global_path = get_state_path(project_root)
        client_path = client_state_path(project_root, client_id)
        global_lines = global_path.read_text(encoding="utf-8").strip().splitlines()
        client_lines = client_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(global_lines), 1)
        self.assertEqual(len(client_lines), 1)
        self.assertIn("file_tracked", global_lines[0])
        self.assertIn(client_id, global_lines[0])
        self.assertIn("file_tracked", client_lines[0])


if __name__ == "__main__":
    unittest.main()
