import unittest
import shutil
from unittest.mock import patch

from claude_auto_review.paths import (
    CLIENTS_DIR,
    get_client_runtime_dir,
    get_log_path,
    get_state_path,
    normalize_relative_path,
)

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

    def test_get_client_runtime_dir_refreshes_deleted_cached_path(self):
        project_root = self.temp_project()
        client_id = "session-a"
        first = get_client_runtime_dir(project_root, client_id)
        first.mkdir(parents=True)
        self.assertTrue(first.exists())

        expected = project_root / CLIENTS_DIR / "client-fresh-session-a"
        shutil.rmtree(first)

        with patch("claude_auto_review.client_dirs._timestamped_client_runtime_dir", return_value=expected):
            result = get_client_runtime_dir(project_root, client_id)

        self.assertEqual(result, expected)

    def test_get_client_runtime_dir_keeps_timestamped_client_name(self):
        project_root = self.temp_project()
        client_name = "client-20260514-173035_session-a"

        result = get_client_runtime_dir(project_root, client_name)

        self.assertEqual(result, project_root / CLIENTS_DIR / client_name)


