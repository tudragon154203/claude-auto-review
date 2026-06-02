import os
import unittest
import unittest.mock as mock
from pathlib import Path

from claude_auto_review.runtime.client_dirs import get_client_id
from claude_auto_review.paths.path_utils import get_project_root
from claude_auto_review.timestamps import local_now_iso

from tests.unit.state.support import StateTestCase


class TestClientId(StateTestCase, unittest.TestCase):

    def test_get_client_id_uses_session_id_from_env(self):
        with mock.patch.dict(os.environ, {"CLAUDE_SESSION_ID": "fixed-session"}):
            result = get_client_id()
        self.assertEqual(result, "fixed-session")

    def test_get_client_id_uses_stdin_session_id(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = get_client_id("hook-session-123")
        self.assertEqual(result, "hook-session-123")

    def test_get_client_id_stdin_overrides_env(self):
        with mock.patch.dict(os.environ, {"CLAUDE_SESSION_ID": "env-session"}):
            result = get_client_id("stdin-session")
        self.assertEqual(result, "stdin-session")
        self.assertNotIn("env-session", result)

    def test_get_client_id_fallback_hostname_pid(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = get_client_id()
            # Should match YYYYMMDD-HHMMSS_hostname-pid
            self.assertRegex(result, r"^\d{8}-\d{6}_.+-\d+$")

    def test_get_client_id_uses_unknown_when_hostname_lookup_fails(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("claude_auto_review.runtime.client_dirs.socket.gethostname", side_effect=OSError("boom")):
                result = get_client_id()

        self.assertRegex(result, r"^\d{8}-\d{6}_unknown-\d+$")

    def test_get_project_root_prefers_environment_variable(self):
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(Path.cwd())}, clear=True):
            self.assertEqual(get_project_root(), Path.cwd().resolve())

    def test_local_now_iso_returns_timestamp_string(self):
        value = local_now_iso()
        self.assertIsInstance(value, str)
        self.assertIn("T", value)

    def test_client_ids_are_time_ordered(self):
        import time
        with mock.patch.dict(os.environ, {}, clear=True):
            id_a = get_client_id()
            time.sleep(1)
            id_b = get_client_id()
        self.assertLess(id_a, id_b)
