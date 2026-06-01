import unittest

from claude_auto_review.state.classification_record import ClassificationRecord
from claude_auto_review.state.edit_record import EditRecord, StopBlockedRecord
from claude_auto_review.state.file_record import ReviewFileRecord
from claude_auto_review.state.models import FileHash
from claude_auto_review.state.review_records import (
    ReviewAutocompleteRecord,
    ReviewCompletedRecord,
    ReviewMetadata,
)


class TestStateModels(unittest.TestCase):
    def test_review_metadata_round_trips_nested_files(self):
        data = {
            "timestamp": "2026-05-05T08:00:00+07:00",
            "type": "review",
            "reviewId": "rev-1",
            "reviewPath": "reviews/rev-1.md",
            "files": [
                {"file": "src/a.ts", "hash": "aaa"},
                {"file": "src/b.ts", "hash": "bbb"},
            ],
            "clientId": "client-a",
            "status": "pending",
        }

        entry = ReviewMetadata.from_dict(data)

        self.assertEqual(
            entry,
            ReviewMetadata(
                timestamp=data["timestamp"],
                reviewId="rev-1",
                reviewPath="reviews/rev-1.md",
                files=[ReviewFileRecord(file="src/a.ts", hash="aaa"), ReviewFileRecord(file="src/b.ts", hash="bbb")],
                clientId="client-a",
                status="pending",
            ),
        )
        self.assertEqual(entry.to_dict(), data)

    def test_review_completed_round_trips_nested_files(self):
        data = {
            "timestamp": "2026-05-05T08:00:00+07:00",
            "type": "review_completed",
            "reviewId": "rev-2",
            "files": [{"file": "src/a.ts", "hash": "aaa"}],
            "clientId": "client-b",
            "duration": "1m 2s",
            "durationSeconds": 62.5,
        }

        entry = ReviewCompletedRecord.from_dict(data)

        self.assertEqual(
            entry,
            ReviewCompletedRecord(
                timestamp=data["timestamp"],
                reviewId="rev-2",
                files=[ReviewFileRecord(file="src/a.ts", hash="aaa")],
                clientId="client-b",
                duration="1m 2s",
                durationSeconds=62.5,
            ),
        )
        self.assertEqual(entry.to_dict(), data)

    def test_from_dict_helpers_preserve_scalar_event_shapes(self):
        edit_data = {
            "timestamp": "t",
            "type": "edit",
            "file": "a.ts",
            "hash": "1",
            "reviewed": True,
            "deleted": True,
            "reviewId": "r",
        }
        blocked_data = {"timestamp": "t", "type": "stop_blocked", "reason": "x", "reviewId": "r", "files": ["a.ts"]}
        classified_data = {
            "timestamp": "t",
            "type": "last_assistant_message_classified",
            "status": "complete",
            "reason": "ok",
            "latencyMs": 12,
            "messageChars": 34,
            "model": "haiku",
            "baseUrl": "https://example.test",
            "httpStatus": 200,
            "debugResponse": "trace",
        }

        self.assertEqual(EditRecord.from_dict(edit_data).to_dict(), edit_data)
        self.assertEqual(StopBlockedRecord.from_dict(blocked_data).to_dict(), blocked_data)
        self.assertEqual(ClassificationRecord.from_dict(classified_data).to_dict(), classified_data)

    def test_review_autocomplete_round_trips(self):
        data = {
            "timestamp": "2026-05-05T08:01:00+07:00",
            "type": "review_autocomplete",
            "reviewId": "rev-1",
            "status": "empty_stdout",
            "returncode": 0,
            "stdout_len": 0,
        }
        record = ReviewAutocompleteRecord.from_dict(data)
        self.assertEqual(record.reviewId, "rev-1")
        self.assertEqual(record.status, "empty_stdout")
        self.assertEqual(record.returncode, 0)
        self.assertEqual(record.stdout_len, 0)
        self.assertEqual(record.to_dict()["type"], "review_autocomplete")

    def test_review_autocomplete_from_dict_requires_fields(self):
        with self.assertRaises(KeyError):
            ReviewAutocompleteRecord.from_dict({"timestamp": "t"})

    def test_review_autocomplete_to_dict_omits_none_returncode(self):
        record = ReviewAutocompleteRecord(
            timestamp="2026-05-05T08:01:00+07:00",
            reviewId="rev-1",
            status="cli_not_found",
        )
        d = record.to_dict()
        self.assertNotIn("returncode", d)
        self.assertEqual(d["stdout_len"], 0)

    def test_review_autocomplete_to_dict_includes_optional_fields(self):
        record = ReviewAutocompleteRecord(
            timestamp="2026-05-05T08:01:00+07:00",
            reviewId="rev-1",
            status="timeout",
            returncode=1,
            stdout_len=500,
        )
        d = record.to_dict()
        self.assertEqual(d["returncode"], 1)
        self.assertEqual(d["stdout_len"], 500)

    def test_file_hash_validates_eight_character_sha_prefix(self):
        self.assertEqual(str(FileHash("ABCDEF12")), "abcdef12")
        self.assertEqual(FileHash("abcdef12").value, "abcdef12")

    def test_file_hash_rejects_invalid_values(self):
        for value in ("", "abc", "abcdef123", "zzzzzzzz"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    FileHash(value)
