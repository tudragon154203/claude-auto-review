import sys
import unittest
from pathlib import Path

from claude_auto_review.bootstrap import ensure_repo_root_on_path


class TestBootstrap(unittest.TestCase):
    def test_ensure_repo_root_on_path_inserts_when_missing(self):
        repo_root = Path(__file__).resolve().parents[3]
        repo_root_str = str(repo_root)
        had_it = repo_root_str in sys.path
        if had_it:
            sys.path.remove(repo_root_str)
        try:
            ensure_repo_root_on_path()
            self.assertIn(repo_root_str, sys.path)
        finally:
            if had_it and repo_root_str not in sys.path:
                sys.path.insert(0, repo_root_str)

    def test_ensure_repo_root_on_path_idempotent(self):
        repo_root_str = str(Path(__file__).resolve().parents[3])
        before = sys.path.count(repo_root_str)
        ensure_repo_root_on_path()
        ensure_repo_root_on_path()
        after = sys.path.count(repo_root_str)
        self.assertLessEqual(after - before, 1)


if __name__ == "__main__":
    unittest.main()