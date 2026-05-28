import unittest

from claude_auto_review.state.models import EditRecord, ReviewMetadata
from claude_auto_review.state.store.parsing import parse_event


class TestParseEvent(unittest.TestCase):
    def test_parses_edit_event(self):
        raw = {"type": "edit", "timestamp": "2026-05-05T08:00:00+07:00", "file": "a.ts", "hash": "aaa"}
        result = parse_event(raw)
        self.assertIsInstance(result, EditRecord)
        self.assertEqual(result.file, "a.ts")
        self.assertEqual(result.hash, "aaa")

    def test_parses_review_event(self):
        raw = {
            "type": "review",
            "timestamp": "2026-05-05T08:00:00+07:00",
            "reviewId": "rev-1",
            "reviewPath": "reviews/rev-1.md",
            "files": [{"file": "a.ts", "hash": "aaa"}],
            "clientId": "c",
            "status": "pending",
        }
        result = parse_event(raw)
        self.assertIsInstance(result, ReviewMetadata)
        self.assertEqual(result.reviewId, "rev-1")

    def test_returns_none_for_unknown_type(self):
        raw = {"type": "unknown_type", "timestamp": "2026-05-05T08:00:00+07:00"}
        self.assertIsNone(parse_event(raw))

    def test_returns_none_for_non_dict(self):
        self.assertIsNone(parse_event("not-a-dict"))
        self.assertIsNone(parse_event(None))
        self.assertIsNone(parse_event(123))

    def test_returns_none_for_missing_required_fields(self):
        raw = {"type": "edit", "timestamp": "2026-05-05T08:00:00+07:00"}
        self.assertIsNone(parse_event(raw))  # missing file and hash

    def test_returns_none_for_edit_with_missing_hash(self):
        raw = {"type": "edit", "timestamp": "2026-05-05T08:00:00+07:00", "file": "a.ts"}
        self.assertIsNone(parse_event(raw))

    def test_returns_none_for_edit_with_missing_file(self):
        raw = {"type": "edit", "timestamp": "2026-05-05T08:00:00+07:00", "hash": "aaa"}
        self.assertIsNone(parse_event(raw))

    def test_returns_none_for_review_with_invalid_files(self):
        raw = {
            "type": "review",
            "timestamp": "2026-05-05T08:00:00+07:00",
            "reviewId": "rev-1",
            "reviewPath": "reviews/rev-1.md",
            "files": [{"wrong_key": "a.ts"}],
            "clientId": "c",
            "status": "pending",
        }
        self.assertIsNone(parse_event(raw))

    def test_returns_none_for_review_autocomplete_with_missing_status(self):
        raw = {
            "type": "review_autocomplete",
            "timestamp": "2026-05-05T08:00:00+07:00",
            "reviewId": "rev-1",
            # missing status
        }
        self.assertIsNone(parse_event(raw))

    def test_returns_none_for_corrupt_json_line(self):
        raw = {"type": "edit", "timestamp": "2026-05-05T08:00:00+07:00"}
        result = parse_event(raw)
        self.assertIsNone(result)

    def test_returns_none_for_edit_with_missing_timestamp(self):
        raw = {"type": "edit", "file": "a.ts", "hash": "aaa"}
        self.assertIsNone(parse_event(raw))


if __name__ == "__main__":
    unittest.main()
