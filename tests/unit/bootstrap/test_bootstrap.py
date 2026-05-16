import sys
import unittest
from pathlib import Path

from claude_auto_review.utils.bootstrap import ensure_repo_root_on_path


class TestBootstrap(unittest.TestCase):
    def test_ensure_repo_root_on_path_is_noop(self):
        before = list(sys.path)
        ensure_repo_root_on_path()
        self.assertEqual(sys.path, before)

    def test_ensure_repo_root_on_path_idempotent(self):
        ensure_repo_root_on_path()
        before = list(sys.path)
        ensure_repo_root_on_path()
        self.assertEqual(sys.path, before)


if __name__ == "__main__":
    unittest.main()
