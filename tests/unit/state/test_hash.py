import hashlib
import tempfile
import unittest
from pathlib import Path

from claude_auto_review.state import get_file_hash

from tests.unit.state.support import StateTestCase


class TestFileHash(StateTestCase, unittest.TestCase):

    def test_hashes_existing_file_content(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.parent.mkdir()
        target.write_text("export const value = 1;\n", encoding="utf-8")
        expected = hashlib.sha256(target.read_bytes()).hexdigest()[:8]
        self.assertEqual(get_file_hash("src/app.ts", project_root), expected)

    def test_get_file_hash_returns_none_for_nonexistent_path(self):
        result = get_file_hash("nonexistent.ts", self.temp_project())
        self.assertIsNone(result)

    def test_get_file_hash_returns_none_for_outside_project(self):
        result = get_file_hash(str(Path(tempfile.mkdtemp()) / "outside.ts"), self.temp_project())
        self.assertIsNone(result)


