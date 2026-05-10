import json
import sys
import unittest
from pathlib import Path

from tests.support import TempProjectMixin

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.state import (
    append_state,
    append_review_started,
    client_reviews_dir,
    client_state_path,
    ensure_client_runtime,
    get_client_runtime_dir,
    get_unreviewed_files,
    load_state,
    mark_files_reviewed,
    pending_reviews_for_entries,
    was_hash_reviewed,
)


class ConcurrencyTests(TempProjectMixin, unittest.TestCase):

    def ensure_client(self, project_root, client_id):
        ensure_client_runtime(project_root, client_id)
        return project_root

    def test_two_clients_do_not_share_state(self):
        """Edits from session A must not appear in session B's state."""
        project_root = self.temp_project()
        client_a = "client-alpha"
        client_b = "client-beta"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        append_state(
            {"type": "edit", "file": "src/a.ts", "hash": "aaaa1111", "timestamp": "2026-05-09T10:00:00Z", "reviewed": False},
            project_root,
            client_id=client_a,
        )
        append_state(
            {"type": "edit", "file": "src/b.ts", "hash": "bbbb2222", "timestamp": "2026-05-09T11:00:00Z", "reviewed": False},
            project_root,
            client_id=client_b,
        )

        state_a = load_state(project_root, client_a)
        state_b = load_state(project_root, client_b)

        self.assertEqual(len(state_a), 1)
        self.assertEqual(state_a[0]["file"], "src/a.ts")
        self.assertEqual(len(state_b), 1)
        self.assertEqual(state_b[0]["file"], "src/b.ts")

    def test_client_isolation_for_reviews(self):
        """Reviews scoped to a client must not affect another client's stop check."""
        project_root = self.temp_project()
        client_a = "client-alpha"
        client_b = "client-beta"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        entries_a = [
            {"type": "edit", "file": "shared.ts", "hash": "hash1", "timestamp": "2026-05-09T12:00:00Z", "reviewed": False}
        ]
        entries_b = [
            {"type": "edit", "file": "shared.ts", "hash": "hash2", "timestamp": "2026-05-09T13:00:00Z", "reviewed": False}
        ]

        append_review_started(entries_a, "rev-a", "dummy-a.md", project_root, client_id=client_a)
        append_review_started(entries_b, "rev-b", "dummy-b.md", project_root, client_id=client_b)

        state_a = load_state(project_root, client_a)
        state_b = load_state(project_root, client_b)

        pending_a = pending_reviews_for_entries(state_a, entries_a)
        pending_b = pending_reviews_for_entries(state_b, entries_b)

        self.assertEqual(len(pending_a), 1, "Client A should see exactly one pending review")
        self.assertEqual(len(pending_b), 1, "Client B should see exactly one pending review")
        self.assertNotEqual(pending_a[0]["reviewId"], pending_b[0]["reviewId"], "Different reviews per client")

    def test_unreviewed_files_scoped_to_client(self):
        """get_unreviewed_files must only include the current client's unreviewed hashes."""
        project_root = self.temp_project()
        client_a = "client-a"
        client_b = "client-b"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        common = {"type": "edit", "file": "common.ts", "timestamp": "2026-05-09T14:00:00Z"}
        append_state({**common, "hash": "aaa", "reviewed": False}, project_root, client_id=client_a)
        append_state({**common, "hash": "bbb", "reviewed": True, "reviewId": "rev-b"}, project_root, client_id=client_b)

        unreviewed_a = get_unreviewed_files(load_state(project_root, client_a))
        unreviewed_b = get_unreviewed_files(load_state(project_root, client_b))

        self.assertEqual(len(unreviewed_a), 1)
        self.assertEqual(unreviewed_a[0]["file"], "common.ts")
        self.assertEqual(unreviewed_a[0]["hash"], "aaa")
        self.assertEqual(len(unreviewed_b), 0, "Client B should have no unreviewed files")

    def test_marking_reviewed_is_isolated(self):
        """Marking files reviewed in client A must not mark them reviewed for client B."""
        project_root = self.temp_project()
        client_a = "client-a"
        client_b = "client-b"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        entry = {"type": "edit", "file": "isolated.ts", "hash": "deadbeef", "timestamp": "2026-05-09T15:00:00Z", "reviewed": False}
        append_state(entry, project_root, client_id=client_a)
        append_state(entry, project_root, client_id=client_b)

        state_a_before = load_state(project_root, client_a)
        state_b_before = load_state(project_root, client_b)
        self.assertFalse(was_hash_reviewed(state_a_before, "isolated.ts", "deadbeef"))
        self.assertFalse(was_hash_reviewed(state_b_before, "isolated.ts", "deadbeef"))

        mark_files_reviewed([entry], "rev-a", project_root, client_id=client_a)

        state_a_after = load_state(project_root, client_a)
        state_b_after = load_state(project_root, client_b)

        self.assertTrue(was_hash_reviewed(state_a_after, "isolated.ts", "deadbeef"), "Client A file should be marked reviewed")
        self.assertFalse(was_hash_reviewed(state_b_after, "isolated.ts", "deadbeef"), "Client B file must remain unreviewed")

    def test_client_state_files_are_separate(self):
        """Each client's state.jsonl file must live in its own directory."""
        project_root = self.temp_project()
        client_a = "client-a"
        client_b = "client-b"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        append_state(
            {"type": "edit", "file": "a.ts", "hash": "aaa", "timestamp": "2026-05-09T09:00:00Z", "reviewed": False},
            project_root,
            client_id=client_a,
        )
        append_state(
            {"type": "edit", "file": "b.ts", "hash": "bbb", "timestamp": "2026-05-09T09:30:00Z", "reviewed": False},
            project_root,
            client_id=client_b,
        )

        path_a = client_state_path(project_root, client_a)
        path_b = client_state_path(project_root, client_b)

        self.assertTrue(path_a.exists(), f"Client A state file should exist at {path_a}")
        self.assertTrue(path_b.exists(), f"Client B state file should exist at {path_b}")
        self.assertNotEqual(path_a, path_b)

    def test_multiple_edits_ordered_per_client(self):
        """get_unreviewed_files should return the latest unreviewed hash per file for each client."""
        project_root = self.temp_project()
        client_a = "client-a"
        self.ensure_client(project_root, client_a)

        append_state(
            {"type": "edit", "file": "evolving.ts", "hash": "v1", "timestamp": "2026-05-09T16:00:00Z", "reviewed": False},
            project_root,
            client_id=client_a,
        )
        append_state(
            {"type": "edit", "file": "evolving.ts", "hash": "v2", "timestamp": "2026-05-09T17:00:00Z", "reviewed": False},
            project_root,
            client_id=client_a,
        )
        append_state(
            {"type": "edit", "file": "evolving.ts", "hash": "v3", "timestamp": "2026-05-09T18:00:00Z", "reviewed": True, "reviewId": "rev"},
            project_root,
            client_id=client_a,
        )
        append_state(
            {"type": "edit", "file": "evolving.ts", "hash": "v4", "timestamp": "2026-05-09T19:00:00Z", "reviewed": False},
            project_root,
            client_id=client_a,
        )

        unreviewed = get_unreviewed_files(load_state(project_root, client_a))
        self.assertEqual(len(unreviewed), 1)
        self.assertEqual(unreviewed[0]["file"], "evolving.ts")
        self.assertEqual(unreviewed[0]["hash"], "v4")

    def test_review_entries_include_client_id(self):
        """append_review_started should embed the clientId field in the entry."""
        project_root = self.temp_project()
        client_id = "client-with-id"
        self.ensure_client(project_root, client_id)

        entries = [
            {"type": "edit", "file": "file1.ts", "hash": "h1", "timestamp": "2026-05-09T20:00:00Z", "reviewed": False}
        ]
        review_path = client_reviews_dir(project_root, client_id) / "review-test.md"
        append_review_started(entries, "rev-test", review_path, project_root, client_id=client_id)

        state = load_state(project_root, client_id)
        review_entry = next(e for e in state if e.get("type") == "review")
        self.assertEqual(review_entry["clientId"], client_id)
        self.assertEqual(review_entry["reviewId"], "rev-test")
        self.assertEqual(len(review_entry["files"]), 1)
        self.assertEqual(review_entry["files"][0]["file"], "file1.ts")

    def test_stop_hook_blocking_logic_per_client(self):
        """Stop hook logic (using state + pending_reviews) applies per client only."""
        # Simulate two clients: A has unreviewed edits + pending review; B just has unreviewed edits
        project_root = self.temp_project()
        client_a = "stopper-a"
        client_b = "stopper-b"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        entry_a = {"type": "edit", "file": "a.ts", "hash": "hash-a", "timestamp": "2026-05-09T21:00:00Z", "reviewed": False}
        entry_b = {"type": "edit", "file": "b.ts", "hash": "hash-b", "timestamp": "2026-05-09T22:00:00Z", "reviewed": False}

        append_state(entry_a, project_root, client_id=client_a)
        append_state(entry_b, project_root, client_id=client_b)

        # Client A also creates a pending review
        append_review_started([entry_a], "rev-a-pending", "dummy-a.md", project_root, client_id=client_a)

        state_a = load_state(project_root, client_a)
        state_b = load_state(project_root, client_b)

        unreviewed_a = get_unreviewed_files(state_a)
        unreviewed_b = get_unreviewed_files(state_b)

        self.assertEqual(len(unreviewed_a), 1)
        self.assertEqual(len(unreviewed_b), 1)

        pending_a = pending_reviews_for_entries(state_a, unreviewed_a)
        pending_b = pending_reviews_for_entries(state_b, unreviewed_b)

        self.assertEqual(len(pending_a), 1, "Client A should see its own pending review")
        self.assertEqual(len(pending_b), 0, "Client B should NOT see client A's pending review")


if __name__ == "__main__":
    unittest.main()

