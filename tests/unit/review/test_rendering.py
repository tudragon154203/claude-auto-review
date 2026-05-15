import tempfile
import unittest
from pathlib import Path

from claude_auto_review.state.models import ReviewFileRecord
from claude_auto_review.utils.datetime_utils import parse_iso_timestamp
from claude_auto_review.review.rendering import (
    _format_file_snapshot,
    _format_missing_file_snapshot,
    _read_text_with_limit,
    _review_context,
    _snapshot_section,
    current_file_snapshots,
    format_file_list,
    format_review_timestamp,
)


class TestReadTextWithLimit(unittest.TestCase):
    def test_reads_entire_file_when_under_limit(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("hello world")
            path = f.name
        try:
            result = _read_text_with_limit(path, 100)
            self.assertEqual(result, "hello world")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_truncates_when_over_limit(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("a" * 50)
            path = f.name
        try:
            result = _read_text_with_limit(path, 10)
            self.assertEqual(len(result), 10)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_zero_max_chars_reads_nothing(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write("content")
            path = f.name
        try:
            result = _read_text_with_limit(path, 0)
            self.assertEqual(len(result), 0)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            path = f.name
        try:
            result = _read_text_with_limit(path, 100)
            self.assertEqual(result, "")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reads_partially_larger_than_chunk_size(self):
        content = "x" * 20000
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            result = _read_text_with_limit(path, 20000)
            self.assertEqual(len(result), 20000)
            self.assertTrue(result.startswith("x" * 20000))
        finally:
            Path(path).unlink(missing_ok=True)


class TestFormatReviewTimestamp(unittest.TestCase):
    def test_formats_utc_timestamp(self):
        timestamp = "2024-01-01T12:00:00+00:00"
        result = format_review_timestamp(timestamp)
        ts = parse_iso_timestamp(timestamp).astimezone()
        offset = ts.strftime("%z")
        offset = f"{offset[:3]}:{offset[3:]}" if offset else ""
        expected = f"{ts.strftime('%Y-%m-%d | %H:%M:%S')} {offset}".rstrip()
        self.assertEqual(result, expected)

    def test_formats_positive_offset(self):
        # We check formatting via real timezone conversion so test is env-stable
        timestamp = "2024-06-15T08:30:00+07:00"
        result = format_review_timestamp(timestamp)
        ts = parse_iso_timestamp(timestamp).astimezone()
        offset = ts.strftime("%z")
        offset = f"{offset[:3]}:{offset[3:]}" if offset else ""
        expected = f"{ts.strftime('%Y-%m-%d | %H:%M:%S')} {offset}".rstrip()
        self.assertEqual(result, expected)

    def test_z_suffix_works(self):
        self.assertEqual(
            format_review_timestamp("2024-01-01T12:00:00Z"),
            format_review_timestamp("2024-01-01T12:00:00+00:00"),
        )


class TestFormatFileList(unittest.TestCase):
    def test_formats_single_entry(self):
        entries = [ReviewFileRecord(file="src/a.ts", hash="abc123")]
        result = format_file_list(entries)
        self.assertEqual(result, "- src/a.ts (hash: abc123)")

    def test_formats_multiple_entries(self):
        entries = [
            ReviewFileRecord(file="src/a.ts", hash="aaa"),
            ReviewFileRecord(file="src/b.ts", hash="bbb"),
        ]
        result = format_file_list(entries)
        self.assertEqual(result, "- src/a.ts (hash: aaa)\n- src/b.ts (hash: bbb)")

    def test_empty_entries(self):
        self.assertEqual(format_file_list([]), "")


class TestReviewContext(unittest.TestCase):
    def test_returns_timestamp_and_file_list(self):
        entries = [ReviewFileRecord(file="x.ts", hash="111")]
        ts, fl = _review_context(entries, "2024-01-01T12:00:00+00:00")
        self.assertIn("2024-01-01", ts)
        self.assertIn("x.ts", fl)


class TestFormatFileSnapshot(unittest.TestCase):
    def test_formats_content_within_limit(self):
        result = _format_file_snapshot("src/a.ts", "content here")
        expected = "## src/a.ts\n\n```\ncontent here\n```"
        self.assertEqual(result, expected)

    def test_truncates_content_over_limit(self):
        content = "x" * 100
        result = _format_file_snapshot("src/a.ts", content, max_chars=10)
        self.assertIn("[truncated at 10 characters]", result)
        self.assertIn("x" * 10, result)
        self.assertNotIn("x" * 11, result)


class TestFormatMissingFileSnapshot(unittest.TestCase):
    def test_format_missing_file_snapshot(self):
        result = _format_missing_file_snapshot("deleted.ts")
        self.assertIn("deleted.ts", result)
        self.assertIn("File does not currently exist.", result)


class TestSnapshotSection(unittest.TestCase):
    def test_missing_file_returns_missing_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            result = _snapshot_section("nope.ts", project_root, 100)
            self.assertIn("nope.ts", result)
            self.assertIn("File does not currently exist.", result)

    def test_existing_file_returns_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            file_path = project_root / "src" / "a.ts"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("content", encoding="utf-8")
            result = _snapshot_section("src/a.ts", project_root, 100)
            self.assertIn("src/a.ts", result)
            self.assertIn("content", result)


class TestCurrentFileSnapshots(unittest.TestCase):
    def test_empty_files_list_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(current_file_snapshots([], Path(tmpdir)), "")

    def test_single_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "a.ts").write_text("hello", encoding="utf-8")
            result = current_file_snapshots(["a.ts"], project_root)
            self.assertIn("a.ts", result)
            self.assertIn("hello", result)

    def test_multiple_files_separated_by_newlines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "a.ts").write_text("alpha", encoding="utf-8")
            (project_root / "b.ts").write_text("beta", encoding="utf-8")
            result = current_file_snapshots(["a.ts", "b.ts"], project_root)
            self.assertIn("a.ts", result)
            self.assertIn("b.ts", result)
            self.assertIn("alpha", result)
            self.assertIn("beta", result)
