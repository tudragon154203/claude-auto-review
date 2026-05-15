import unittest

from claude_auto_review.runtime.core.client_dirs import client_state_path
from claude_auto_review.paths.core.path_utils import get_log_path, local_now_iso
from claude_auto_review.runtime.core.events import log_event
from claude_auto_review.runtime.setup import ensure_client_runtime, ensure_runtime
from claude_auto_review.state.core.models import ClassificationRecord, EditRecord, ReviewCompletedRecord, ReviewFileRecord, ReviewMetadata, StopBlockedRecord
from claude_auto_review.state.store.read import get_unreviewed_files, latest_entries_by_file, load_state, reviewed_hashes_by_file, was_hash_reviewed
from claude_auto_review.state.store.write import append_state

from tests.unit.state.support import StateTestCase


class TestStateStore(StateTestCase, unittest.TestCase):

    def test_loads_latest_unreviewed_file_entries(self):
        project_root = self.temp_project()
        ensure_runtime(project_root)
        append_state(EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="11111111"), project_root)
        append_state(EditRecord(timestamp="2026-05-05T09:00:00+07:00", file="a.ts", hash="22222222", reviewed=True, reviewId="rev-1"), project_root)
        append_state(EditRecord(timestamp="2026-05-05T10:00:00+07:00", file="b.ts", hash="33333333"), project_root)

        self.assertEqual(get_unreviewed_files(load_state(project_root))[0].file, "b.ts")

    def test_ignores_corrupt_state_lines(self):
        project_root = self.temp_project()
        client_id = "test-corrupt"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        state_path.write_text('{"type":"edit","file":"a.ts","hash":"1","reviewed":false}\nnot-json\n', encoding="utf-8")
        self.assertEqual(len(load_state(project_root, client_id)), 1)

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
        log_path = get_log_path(project_root)
        self.assertTrue(log_path.exists())
        content = log_path.read_text(encoding="utf-8")
        self.assertIn('"type":"test_event"', content)

    def test_log_event_appends_to_existing_log(self):
        project_root = self.temp_project()
        log_event(project_root, "first")
        log_event(project_root, "second")
        log_path = get_log_path(project_root)
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)

    def test_latest_entries_by_file_handles_missing_timestamp(self):
        state = [
            EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="1"),
            EditRecord(timestamp="2026-05-05T09:00:00+07:00", file="a.ts", hash="2"),
        ]
        result = latest_entries_by_file(state)
        self.assertEqual(result["a.ts"].hash, "2")

    def test_latest_entries_by_file_orders_mixed_timezones_chronologically(self):
        state = [
            EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="older"),
            EditRecord(timestamp="2026-05-05T02:30:00+00:00", file="a.ts", hash="newer"),
        ]
        result = latest_entries_by_file(state)
        self.assertEqual(result["a.ts"].hash, "newer")

    def test_latest_entries_by_file_skips_non_edit_entries(self):
        state = [
            ClassificationRecord(
                timestamp="2026-05-05T08:00:00+07:00",
                status="complete",
                reason="ok",
                latencyMs=10,
                messageChars=42,
                model="haiku",
                baseUrl="https://example.test",
            ),
            EditRecord(timestamp="2026-05-05T09:00:00+07:00", file="b.ts", hash="1"),
        ]
        result = latest_entries_by_file(state)
        self.assertIn("b.ts", result)
        self.assertNotIn("review", result)

    def test_reviewed_hashes_by_file_returns_multiple_hashes_per_file(self):
        state = [
            EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="1", reviewed=True),
            EditRecord(timestamp="2026-05-05T09:00:00+07:00", file="a.ts", hash="2", reviewed=True),
            EditRecord(timestamp="2026-05-05T10:00:00+07:00", file="b.ts", hash="3"),
        ]
        result = reviewed_hashes_by_file(state)
        self.assertEqual(result["a.ts"], {"1", "2"})
        self.assertNotIn("b.ts", result)

    def test_was_hash_reviewed_true(self):
        state = [EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="abc123", reviewed=True)]
        self.assertTrue(was_hash_reviewed(state, "a.ts", "abc123"))

    def test_was_hash_reviewed_false(self):
        state = [EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="abc123")]
        self.assertFalse(was_hash_reviewed(state, "a.ts", "abc123"))

    def test_latest_entries_by_file_skips_non_dict_entries(self):
        state = [
            None,
            "string",
            EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="1"),
        ]
        result = latest_entries_by_file(state)
        self.assertEqual(result["a.ts"].hash, "1")

    def test_load_state_returns_empty_for_missing_file(self):
        project_root = self.temp_project()
        state = load_state(project_root, "no-file-client")
        self.assertEqual(state, [])

    def test_load_state_skips_empty_lines(self):
        project_root = self.temp_project()
        client_id = "empty-line-test"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        state_path.write_text(
            '{"type":"edit","file":"a.ts","hash":"1","reviewed":false}\n\n{"type":"edit","file":"b.ts","hash":"2","reviewed":false}\n',
            encoding="utf-8",
        )
        state = load_state(project_root, client_id)
        self.assertEqual(len(state), 2)

    def test_load_state_parses_review_records(self):
        project_root = self.temp_project()
        client_id = "review-records"
        ensure_client_runtime(project_root, client_id)
        state_path = client_state_path(project_root, client_id)
        state_path.write_text(
            "\n".join(
                [
                    '{"timestamp":"2026-05-05T08:00:00+07:00","type":"review","reviewId":"rev-1","reviewPath":"reviews/rev-1.md","files":[{"file":"src/a.ts","hash":"aaa"}],"clientId":"client-a","status":"pending"}',
                    '{"timestamp":"2026-05-05T08:01:00+07:00","type":"review_completed","reviewId":"rev-1","files":[{"file":"src/a.ts","hash":"aaa"}],"clientId":"client-a","duration":"1m","durationSeconds":60}',
                    '{"timestamp":"2026-05-05T08:02:00+07:00","type":"stop_blocked","reason":"review_pending","reviewId":"rev-1","files":["src/a.ts"]}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        state = load_state(project_root, client_id)

        self.assertIsInstance(state[0], ReviewMetadata)
        self.assertEqual(state[0].files, [ReviewFileRecord(file="src/a.ts", hash="aaa")])
        self.assertIsInstance(state[1], ReviewCompletedRecord)
        self.assertEqual(state[1].files, [ReviewFileRecord(file="src/a.ts", hash="aaa")])
        self.assertIsInstance(state[2], StopBlockedRecord)
