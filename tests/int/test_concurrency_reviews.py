from tests.int.support import ClientIsolationTestCase

from claude_auto_review.runtime.client_dirs import client_reviews_dir
from claude_auto_review.state.models import EditRecord
from claude_auto_review.state.reviews import pending_reviews_for_entries
from claude_auto_review.state.store_read import get_unreviewed_files, load_state
from claude_auto_review.state.store_write import append_review_started, append_state


class ConcurrencyReviewTests(ClientIsolationTestCase):
    def test_client_isolation_for_reviews(self):
        project_root = self.temp_project()
        client_a = "client-alpha"
        client_b = "client-beta"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        entries_a = [EditRecord(type="edit", file="shared.ts", hash="hash1", timestamp="2026-05-09T12:00:00+07:00", reviewed=False)]
        entries_b = [EditRecord(type="edit", file="shared.ts", hash="hash2", timestamp="2026-05-09T13:00:00+07:00", reviewed=False)]

        append_review_started(entries_a, "rev-a", "dummy-a.md", project_root, client_id=client_a)
        append_review_started(entries_b, "rev-b", "dummy-b.md", project_root, client_id=client_b)

        pending_a = pending_reviews_for_entries(load_state(project_root, client_a), entries_a)
        pending_b = pending_reviews_for_entries(load_state(project_root, client_b), entries_b)

        self.assertEqual(len(pending_a), 1)
        self.assertEqual(len(pending_b), 1)
        self.assertNotEqual(pending_a[0].reviewId, pending_b[0].reviewId)

    def test_review_entries_include_client_id(self):
        project_root = self.temp_project()
        client_id = "client-with-id"
        self.ensure_client(project_root, client_id)

        entries = [EditRecord(type="edit", file="file1.ts", hash="h1", timestamp="2026-05-09T20:00:00+07:00", reviewed=False)]
        review_path = client_reviews_dir(project_root, client_id) / "review-test.md"
        append_review_started(entries, "rev-test", review_path, project_root, client_id=client_id)

        state = load_state(project_root, client_id)
        review_entry = next(e for e in state if getattr(e, "type", None) == "review")
        self.assertEqual(review_entry.clientId, client_id)
        self.assertEqual(review_entry.reviewId, "rev-test")
        self.assertEqual(len(review_entry.files), 1)
        self.assertEqual(review_entry.files[0].file, "file1.ts")

    def test_stop_hook_blocking_logic_per_client(self):
        project_root = self.temp_project()
        client_a = "stopper-a"
        client_b = "stopper-b"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        entry_a = EditRecord(type="edit", file="a.ts", hash="hash-a", timestamp="2026-05-09T21:00:00+07:00", reviewed=False)
        entry_b = EditRecord(type="edit", file="b.ts", hash="hash-b", timestamp="2026-05-09T22:00:00+07:00", reviewed=False)

        append_state(entry_a, project_root, client_id=client_a)
        append_state(entry_b, project_root, client_id=client_b)
        append_review_started([entry_a], "rev-a-pending", "dummy-a.md", project_root, client_id=client_a)

        state_a = load_state(project_root, client_a)
        state_b = load_state(project_root, client_b)

        unreviewed_a = get_unreviewed_files(state_a)
        unreviewed_b = get_unreviewed_files(state_b)
        self.assertEqual(len(unreviewed_a), 1)
        self.assertEqual(len(unreviewed_b), 1)

        pending_a = pending_reviews_for_entries(state_a, unreviewed_a)
        pending_b = pending_reviews_for_entries(state_b, unreviewed_b)

        self.assertEqual(len(pending_a), 1)
        self.assertEqual(len(pending_b), 0)
