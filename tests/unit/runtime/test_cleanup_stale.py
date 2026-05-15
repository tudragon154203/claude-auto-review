import os
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.runtime.cleanup_stale import _is_client_state_stale, cleanup_stale_clients
from claude_auto_review.runtime.client_dirs import client_state_path
from claude_auto_review.runtime.setup import ensure_client_runtime

from tests.unit.state.support import StateTestCase


class TestCleanupStaleClients(StateTestCase, unittest.TestCase):

    def test_is_client_state_stale_uses_parent_mtime_when_state_missing(self):
        project_root = self.temp_project()
        client_id = "stale-by-dir"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        if state_path.exists():
            state_path.unlink()

        stale_ts = (project_root.stat().st_mtime - 3 * 24 * 60 * 60)
        os.utime(state_path.parent, (stale_ts, stale_ts))

        self.assertTrue(_is_client_state_stale(state_path, timeout_hours=48))

    def test_cleanup_stale_clients_skips_unreadable_state(self):
        project_root = self.temp_project()
        client_id = "stale-unreadable"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        state_path.write_text("{}", encoding="utf-8")

        with patch("claude_auto_review.state.store_read.read_jsonl_records", side_effect=OSError("boom")):
            removed = cleanup_stale_clients(project_root)

        self.assertEqual(removed, [])
        self.assertTrue(state_path.parent.exists())
