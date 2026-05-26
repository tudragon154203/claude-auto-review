import unittest

from claude_auto_review.state.file_record import (
    _coerce_review_file_entries,
    _parse_review_file_entries,
    ReviewFileRecord
)


class TestFileRecordEdgeCases(unittest.TestCase):

    def test_coerce_review_file_entries_raises_on_invalid_entry(self):
        entries = [
            ReviewFileRecord(file="a.ts", hash="aaa"),
            {"file": "b.ts", "hash": "bbb"},  # Not a ReviewFileRecord
        ]
        with self.assertRaises(ValueError) as cm:
            _coerce_review_file_entries(entries)
        self.assertEqual(str(cm.exception), "files must contain ReviewFileRecord entries")

    def test_parse_review_file_entries_raises_on_invalid_entry(self):
        entries = [
            {"file": "a.ts", "hash": "aaa"},
            "just-a-string",  # Not a dict or ReviewFileRecord
        ]
        with self.assertRaises(ValueError) as cm:
            _parse_review_file_entries(entries)
        self.assertEqual(str(cm.exception), "files must contain file/hash entries")

    def test_parse_review_file_entries_raises_on_missing_keys(self):
        entries = [
            {"file": "a.ts"},  # Missing hash
        ]
        with self.assertRaises(ValueError) as cm:
            _parse_review_file_entries(entries)
        self.assertEqual(str(cm.exception), "files must contain file/hash entries")


if __name__ == "__main__":
    unittest.main()