from claude_auto_review.paths.path_utils import local_now_iso
from claude_auto_review.review.completion import apply_completed_review
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.state.models import EditRecord, ReviewCompletedRecord, ReviewMetadata, StopBlockedRecord
from claude_auto_review.state.reviews.matching import pending_reviews_for_entries
from claude_auto_review.state.store.read import (
    consecutive_stop_blocks,
    get_unreviewed_files,
    load_state,
    was_hash_reviewed,
)
from claude_auto_review.state.store.write import append_review_started, append_state_event, mark_files_reviewed
from tests.int.support import IntegrationTestCase


class IntegrationStateTests(IntegrationTestCase):
    def test_review_started_to_pending_detection_cycle(self):
        project_root = self.temp_project()
        client_id = "review-cycle"
        ensure_client_runtime(project_root, client_id)

        entry = EditRecord(
            timestamp=local_now_iso(),
            file="src/main.ts",
            hash="abc123",
            reviewed=False,
        )
        append_state_event(entry, project_root, client_id=client_id)

        state = load_state(project_root, client_id)
        entries = [e for e in state if isinstance(e, EditRecord)]
        self.assertEqual(len(entries), 1)

        append_review_started(entries, "rev-001", "reviews/rev-001.md", project_root, client_id=client_id)

        state = load_state(project_root, client_id)
        unreviewed = get_unreviewed_files(state)
        self.assertEqual(len(unreviewed), 1)

        reviews = pending_reviews_for_entries(state, entries)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].reviewId, "rev-001")

    def test_mark_files_reviewed_cross_function_consistency(self):
        project_root = self.temp_project()
        client_id = "mark-consistency"
        ensure_client_runtime(project_root, client_id)

        for file, h in [("a.ts", "h1"), ("b.ts", "h2"), ("c.ts", "h3")]:
            append_state_event(
                EditRecord(timestamp=local_now_iso(), file=file, hash=h, reviewed=False),
                project_root,
                client_id=client_id,
            )

        state = load_state(project_root, client_id)
        self.assertEqual(len(get_unreviewed_files(state)), 3)

        mark_files_reviewed(
            [EditRecord(timestamp=local_now_iso(), file="b.ts", hash="h2", reviewed=False)],
            "rev-001",
            project_root,
            client_id=client_id,
        )

        state = load_state(project_root, client_id)
        self.assertTrue(was_hash_reviewed(state, "b.ts", "h2"))
        self.assertFalse(was_hash_reviewed(state, "a.ts", "h1"))
        self.assertFalse(was_hash_reviewed(state, "c.ts", "h3"))

        unreviewed = get_unreviewed_files(state)
        self.assertEqual(len(unreviewed), 2)
        unreviewed_files = {e.file for e in unreviewed}
        self.assertIn("a.ts", unreviewed_files)
        self.assertIn("c.ts", unreviewed_files)

    def test_multiple_clients_state_isolation(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "alice")
        ensure_client_runtime(project_root, "bob")

        append_state_event(
            EditRecord(timestamp=local_now_iso(), file="alice.txt", hash="1111", reviewed=False),
            project_root,
            client_id="alice",
        )
        append_state_event(
            EditRecord(timestamp=local_now_iso(), file="bob.txt", hash="2222", reviewed=False),
            project_root,
            client_id="bob",
        )

        state_a = load_state(project_root, "alice")
        state_b = load_state(project_root, "bob")

        files_a = {e.file for e in state_a if isinstance(e, EditRecord)}
        files_b = {e.file for e in state_b if isinstance(e, EditRecord)}

        self.assertIn("alice.txt", files_a)
        self.assertNotIn("bob.txt", files_a)
        self.assertIn("bob.txt", files_b)
        self.assertNotIn("alice.txt", files_b)

    def test_consecutive_stop_blocks_with_reviewed_edit_reset(self):
        project_root = self.temp_project()
        client_id = "stop-blocks-reset"
        ensure_client_runtime(project_root, client_id)

        append_state_event(
            EditRecord(timestamp=local_now_iso(), file="a.ts", hash="h1", reviewed=False),
            project_root,
            client_id=client_id,
        )
        for _ in range(3):
            append_state_event(
                StopBlockedRecord(timestamp=local_now_iso(), reason="x"), project_root, client_id=client_id
            )

        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 3)

        append_state_event(
            EditRecord(timestamp=local_now_iso(), file="a.ts", hash="h1", reviewed=True, reviewId="r1"),
            project_root,
            client_id=client_id,
        )
        state = load_state(project_root, client_id)
        self.assertEqual(consecutive_stop_blocks(state), 0)

    def test_append_review_started_marks_review_state_consistently(self):
        project_root = self.temp_project()
        client_id = "review-state"
        ensure_client_runtime(project_root, client_id)

        entries = [
            EditRecord(timestamp=local_now_iso(), file="f1.ts", hash="a", reviewed=False),
            EditRecord(timestamp=local_now_iso(), file="f2.ts", hash="b", reviewed=False),
        ]
        for e in entries:
            append_state_event(e, project_root, client_id=client_id)

        state_before = load_state(project_root, client_id)
        pending = pending_reviews_for_entries(state_before, state_before)
        self.assertEqual(len(pending), 0)

        append_review_started(entries, "rev-01", "reviews/rev-01.md", project_root, client_id=client_id)

        state_after = load_state(project_root, client_id)
        edit_entries = [e for e in state_after if isinstance(e, EditRecord)]
        pending = pending_reviews_for_entries(state_after, edit_entries)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].reviewId, "rev-01")

    def test_apply_completed_review_records_partial_review_state(self):
        project_root = self.temp_project()
        client_id = "partial-review"
        ensure_client_runtime(project_root, client_id)

        covered_entry = EditRecord(
            timestamp="2026-05-11T23:18:00+07:00",
            file="src/a.ts",
            hash="aaaa1111",
            reviewed=False,
        )
        remaining_entry = EditRecord(
            timestamp="2026-05-11T23:19:00+07:00",
            file="src/b.ts",
            hash="bbbb2222",
            reviewed=False,
        )

        append_state_event(covered_entry, project_root, client_id=client_id)
        append_review_started([covered_entry], "review-123", "reviews/review-123.md", project_root, client_id=client_id)
        append_state_event(remaining_entry, project_root, client_id=client_id)

        remaining = apply_completed_review(project_root, client_id, "review-123", [covered_entry])

        self.assertEqual([entry.file for entry in remaining], ["src/b.ts"])

        state = load_state(project_root, client_id)
        review_entries = [entry for entry in state if isinstance(entry, ReviewMetadata)]
        completed_reviews = [entry for entry in state if isinstance(entry, ReviewCompletedRecord)]
        blocked_entries = [entry for entry in state if isinstance(entry, StopBlockedRecord)]

        self.assertEqual(review_entries[-1].status, "completed")
        self.assertEqual(review_entries[-1].reviewId, "review-123")
        self.assertEqual(completed_reviews[-1].reviewId, "review-123")
        self.assertEqual(completed_reviews[-1].files[0].file, "src/a.ts")
        self.assertEqual(blocked_entries[-1].reason, "partial_review")
        self.assertEqual(blocked_entries[-1].files, ["src/b.ts"])
        self.assertTrue(was_hash_reviewed(state, "src/a.ts", "aaaa1111"))
        self.assertFalse(was_hash_reviewed(state, "src/b.ts", "bbbb2222"))
