import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.runtime.core.client_dirs import client_reviews_dir, client_run_dir
from claude_auto_review.runtime.setup import ensure_client_runtime
from claude_auto_review.state.models import EditRecord
from claude_auto_review.review.prompting.flow import (
    _review_id_from_timestamp,
    _review_prompt_paths,
    create_review_prompt_files,
)
from claude_auto_review.stop.orchestration.core.context import RuntimeContext


class TestReviewPromptFlow(unittest.TestCase):
    def test_review_id_from_timestamp_includes_microseconds(self):
        self.assertEqual(_review_id_from_timestamp("2026-05-11T12:34:56+07:00"), "rev-20260511123456000000")

    def test_review_prompt_paths_place_files_under_expected_directories(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-prompt-flow-"))
        ctx = RuntimeContext(project_root=project_root, client_id="1")
        review_path, prompt_path = _review_prompt_paths(ctx, "rev-123")

        expected_reviews = client_reviews_dir(project_root, "1")
        self.assertEqual(review_path.parent, expected_reviews)
        self.assertEqual(review_path.name, "review-rev-123.md")
        expected_run = client_run_dir(project_root, "1")
        self.assertEqual(prompt_path.parent, expected_run)
        self.assertEqual(prompt_path.name, "review-rev-123-prompt.md")

    def test_create_review_prompt_files_writes_prompt_and_review_files(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-prompt-flow-"))
        client_id = "client-a"
        review_rules = project_root / ".claude" / "claude-auto-review" / "review-rules.md"
        review_rules.parent.mkdir(parents=True, exist_ok=True)
        review_rules.write_text("Project rules.\n", encoding="utf-8")

        source_file = project_root / "src" / "app.ts"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text("const value = 1;\n", encoding="utf-8")
        ensure_client_runtime(project_root, client_id)

        with patch("claude_auto_review.review.prompting.flow.local_now_iso", return_value="2026-05-11T12:34:56+07:00"):
            ctx = RuntimeContext(
                project_root=project_root,
                client_id=client_id,
                settings={"rulesFile": str(review_rules)},
            )
            artifacts = create_review_prompt_files(
                ctx,
                [EditRecord(timestamp="2026-05-11T12:34:56+07:00", file="src/app.ts", hash="abc123")],
                settings=ctx.settings,
            )

        self.assertEqual(artifacts.review_id, "rev-20260511123456000000")
        self.assertEqual(artifacts.files, ["src/app.ts"])
        self.assertTrue(artifacts.prompt_path.exists())
        self.assertTrue(artifacts.review_path.exists())

        prompt_content = artifacts.prompt_path.read_text(encoding="utf-8")
        review_content = artifacts.review_path.read_text(encoding="utf-8")

        self.assertIn("Project rules.", prompt_content)
        self.assertIn("Git diff unavailable. Review the current file contents directly.", prompt_content)
        self.assertIn("## Current File Snapshots", prompt_content)
        self.assertIn("const value = 1;", prompt_content)
        self.assertIn("No findings yet. This file is a placeholder until Claude completes the review.", review_content)
        self.assertIn("Pending. Claude must complete this review from", review_content)
