import tempfile
import unittest
from pathlib import Path

from claude_auto_review.paths.uri_utils import _normalize_file_uri, normalize_relative_path


class TestNormalizeFileUri(unittest.TestCase):
    def test_leaves_non_file_paths_unchanged(self):
        self.assertEqual(_normalize_file_uri("src/app.ts"), "src/app.ts")

    def test_normalizes_file_scheme_path(self):
        self.assertEqual(_normalize_file_uri("file:///tmp/src/app.ts"), "/tmp/src/app.ts")

    def test_normalizes_localhost_file_uri(self):
        self.assertEqual(_normalize_file_uri("file://localhost/tmp/src/app.ts"), "/tmp/src/app.ts")

    def test_preserves_unc_path(self):
        self.assertEqual(_normalize_file_uri("file://server/share/app.ts"), "//server/share/app.ts")

    def test_windows_drive_uri_round_trips(self):
        # On Windows, file:///C:/path becomes C:/path.
        result = _normalize_file_uri("file:///C:/temp/app.ts")
        self.assertTrue(result.endswith("C:/temp/app.ts") or result.endswith("C:\\temp\\app.ts"))

    def test_file_uri_without_scheme_is_unchanged(self):
        self.assertEqual(_normalize_file_uri("http://example.com/a.ts"), "http://example.com/a.ts")


class TestNormalizeRelativePath(unittest.TestCase):
    def test_returns_none_for_empty_input(self):
        self.assertIsNone(normalize_relative_path(""))

    def test_returns_none_for_path_outside_project(self):
        project_root = Path(tempfile.mkdtemp())
        outside = Path(tempfile.gettempdir()) / "outside.ts"
        self.assertIsNone(normalize_relative_path(outside, project_root))

    def test_normalizes_file_uri_inside_project(self):
        project_root = Path(tempfile.mkdtemp())
        target = project_root / "src" / "app.ts"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("hello", encoding="utf-8")
        self.assertEqual(normalize_relative_path(target.as_uri(), project_root), "src/app.ts")

    def test_returns_none_for_project_root(self):
        project_root = Path(tempfile.mkdtemp())
        self.assertIsNone(normalize_relative_path(project_root, project_root))
