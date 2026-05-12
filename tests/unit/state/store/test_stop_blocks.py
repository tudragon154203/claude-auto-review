import unittest

from claude_auto_review.paths import client_state_path
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.state.store_read import consecutive_stop_blocks, load_state
from claude_auto_review.state.store_write import append_state

from tests.unit.state.support import StateTestCase


class TestStopBlocks(StateTestCase, unittest.TestCase):

    def ensure_client(self, project_root, client_id):
        ensure_client_runtime(project_root, client_id)
        return project_root

    def test_returns_zero_for_empty_state(self):
        project_root = self.temp_project()
        client_id = "client-zero"
        self.ensure_client(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(load_state(project_root, client_id)), 0)

    def test_counts_blocks_since_last_reviewed_edit(self):
        project_root = self.temp_project()
        client_id = "client-batch"
        self.ensure_client(project_root, client_id)
        append_state({"type": "edit", "file": "a.ts", "hash": "1", "reviewed": False}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "no_pending_review"}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        append_state({"type": "edit", "file": "b.ts", "hash": "2", "reviewed": False}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "no_pending_review"}, project_root, client_id=client_id)
        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 4)

    def test_ignores_blocks_before_latest_review_completion(self):
        project_root = self.temp_project()
        client_id = "client-reset"
        self.ensure_client(project_root, client_id)
        append_state({"type": "edit", "file": "x.ts", "hash": "x", "reviewed": False}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        append_state({"type": "edit", "file": "x.ts", "hash": "x", "reviewed": True, "reviewId": "rev-1"}, project_root, client_id=client_id)
        append_state({"type": "edit", "file": "y.ts", "hash": "y", "reviewed": False}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "no_pending_review"}, project_root, client_id=client_id)
        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 1)

    def test_ignores_non_dict_entries(self):
        project_root = self.temp_project()
        client_id = "client-ignore"
        self.ensure_client(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        # Manually corrupt the state file to include non-dict entries
        with state_path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("just a string\nnull\n")
        # Add valid block entries on top
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 2)

    def test_ignores_last_assistant_message_classified_entries(self):
        project_root = self.temp_project()
        client_id = "client-classifier"
        self.ensure_client(project_root, client_id)
        append_state({"type": "edit", "file": "a.ts", "hash": "1", "reviewed": False}, project_root, client_id=client_id)
        append_state({"type": "last_assistant_message_classified", "status": "complete"}, project_root, client_id=client_id)
        append_state({"type": "stop_blocked", "reason": "review_pending"}, project_root, client_id=client_id)
        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 1)


