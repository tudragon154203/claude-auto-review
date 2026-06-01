import unittest

from claude_auto_review.state.records.edit import EditRecord, StopBlockedRecord
from claude_auto_review.state.tracker import StateTracker
from tests.unit.state.support import StateTestCase


class TestStateTracker(StateTestCase, unittest.TestCase):
    def test_track_edit_and_get_unreviewed(self):
        project_root = self.temp_project()
        tracker = StateTracker(project_root=project_root, client_id="tracker")
        edit = EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="src/app.ts", hash="abcdef12")

        tracker.track_edit(edit)

        self.assertEqual(tracker.get_unreviewed(), [edit])

    def test_mark_reviewed_marks_existing_hash_reviewed(self):
        project_root = self.temp_project()
        tracker = StateTracker(project_root=project_root, client_id="tracker")
        edit = EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="src/app.ts", hash="abcdef12")
        tracker.track_edit(edit)

        tracker.mark_reviewed([edit], "rev-1", timestamp="2026-05-05T08:05:00+07:00")

        self.assertEqual(tracker.get_unreviewed(), [])
        self.assertEqual(len(tracker.load().events), 2)

    def test_get_consecutive_blocks_counts_tail_blocks(self):
        project_root = self.temp_project()
        tracker = StateTracker(project_root=project_root, client_id="tracker")
        tracker.track_edit(EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="src/app.ts", hash="abcdef12"))
        tracker.track_edit(EditRecord(timestamp="2026-05-05T08:01:00+07:00", file="src/app.ts", hash="abcdef12"))
        tracker.record_event(StopBlockedRecord(timestamp="2026-05-05T08:02:00+07:00"))
        tracker.record_event(StopBlockedRecord(timestamp="2026-05-05T08:03:00+07:00"))

        self.assertEqual(tracker.get_consecutive_blocks(), 2)

    def test_file_hash_helper_builds_value_object(self):
        self.assertEqual(StateTracker.file_hash("ABCDEF12").value, "abcdef12")


if __name__ == "__main__":
    unittest.main()
