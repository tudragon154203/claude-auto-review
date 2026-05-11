import tempfile
import unittest
from pathlib import Path

from claude_auto_review.install.installer import ensure_gitignore_entries


class TestInstaller(unittest.TestCase):
    def test_ensure_gitignore_entries_replaces_legacy_claude_auto_review_entries(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="claude-auto-review-gitignore-"))
        gitignore_path = temp_dir / ".gitignore"
        gitignore_path.write_text(
            "\n".join(
                [
                    ".claude/",
                    "node_modules/",
                    ".claude/claude-auto-review/clients/*/run/",
                    ".claude/claude-auto-review/clients/*/reviews/",
                    ".claude/claude-auto-review/scripts/",
                    ".claude/claude-auto-review/agents/",
                    ".claude/claude-auto-review/claude-auto-review.log",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        ensure_gitignore_entries(
            gitignore_path,
            [".claude/claude-auto-review/"],
            remove_entries=[
                ".claude/claude-auto-review/clients/*/run/",
                ".claude/claude-auto-review/clients/*/reviews/",
                ".claude/claude-auto-review/scripts/",
                ".claude/claude-auto-review/agents/",
                ".claude/claude-auto-review/claude-auto-review.log",
            ],
        )

        lines = gitignore_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, [".claude/", "node_modules/", ".claude/claude-auto-review/"])


if __name__ == "__main__":
    unittest.main()
