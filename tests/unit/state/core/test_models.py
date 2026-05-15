import unittest

from claude_auto_review.state.core.models import ClassificationRecord, EditRecord, ReviewCompletedRecord, ReviewFileRecord, ReviewMetadata, StopBlockedRecord


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
        edit_data = {"timestamp": "t", "type": "edit", "file": "a.ts", "hash": "1", "reviewed": True, "deleted": True, "reviewId": "r"}
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
