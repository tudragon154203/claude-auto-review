import unittest

from claude_auto_review.paths import get_log_path, get_state_path, normalize_relative_path

from tests.unit.state.support import StateTestCase


class TestPathUtils(StateTestCase, unittest.TestCase):

    def test_normalizes_paths_inside_project_root(self):
        project_root = self.temp_project()
        self.assertEqual(normalize_relative_path("src/app.ts", project_root), "src/app.ts")
        self.assertEqual(normalize_relative_path(project_root / "src" / "app.ts", project_root), "src/app.ts")
        self.assertIsNone(normalize_relative_path(project_root.parent / "outside.ts", project_root))

    def test_normalizes_file_url_paths_inside_project_root(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        self.assertEqual(normalize_relative_path(f"file://{target}", project_root), "src/app.ts")

    def test_normalizes_canonical_file_url_paths_inside_project_root(self):
        project_root = self.temp_project()
        target = (project_root / "src" / "app.ts").resolve().as_posix()
        self.assertEqual(normalize_relative_path(f"file:///{target}", project_root), "src/app.ts")

    def test_rejects_relative_path_traversal_outside_project_root(self):
        project_root = self.temp_project()
        self.assertIsNone(normalize_relative_path("../outside.ts", project_root))

    def test_normalize_relative_path_returns_none_for_empty_string(self):
        project_root = self.temp_project()
        self.assertIsNone(normalize_relative_path("", project_root))
        self.assertIsNone(normalize_relative_path(None, project_root))

    def test_normalize_relative_path_returns_none_for_project_root(self):
        project_root = self.temp_project()
        self.assertIsNone(normalize_relative_path(str(project_root), project_root))

    def test_normalize_relative_path_returns_none_for_empty_relative(self):
        project_root = self.temp_project()
        self.assertIsNone(normalize_relative_path(".", project_root))

    def test_get_state_path_returns_correct_path(self):
        project_root = self.temp_project()
        result = get_state_path(project_root)
        self.assertEqual(result, project_root / ".claude" / "claude-auto-review" / "state.jsonl")

    def test_get_log_path_returns_correct_path(self):
        project_root = self.temp_project()
        result = get_log_path(project_root)
        self.assertEqual(result, project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log")


