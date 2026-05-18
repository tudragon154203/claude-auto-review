import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from claude_auto_review.install.installer import copy_if_changed, ensure_gitignore_entries, _write_text_if_changed


class TestInstaller(unittest.TestCase):
    def test_write_text_if_changed_skips_identical_content(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="claude-auto-review-write-"))
        target = temp_dir / "file.txt"
        target.write_text("same", encoding="utf-8")

        with patch.object(Path, "write_text") as mock_write:
            _write_text_if_changed(target, "same")

        mock_write.assert_not_called()

    def test_copy_if_changed_skips_missing_source(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="claude-auto-review-copy-"))
        source = temp_dir / "missing.txt"
        destination = temp_dir / "dest.txt"

        copy_if_changed(source, destination)

        self.assertFalse(destination.exists())

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
            ],
        )

        lines = gitignore_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, [".claude/", "node_modules/", ".claude/claude-auto-review/"])


if __name__ == "__main__":
    unittest.main()
