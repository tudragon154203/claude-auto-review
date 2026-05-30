import json
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.state.models import EditRecord
from claude_auto_review.stop.feedback_format import (
    build_review_completion_prompt,
    build_review_findings_feedback,
    build_unreviewed_files_string,
    review_feedback_max_chars,
)
from claude_auto_review.stop.response import block_response


class TestFeedback(unittest.TestCase):
    def test_build_unreviewed_files_string(self):
        entries = [
            EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="a.ts", hash="1"),
            EditRecord(timestamp="2026-05-05T08:00:00+07:00", file="b.ts", hash="2"),
        ]
        self.assertEqual(build_unreviewed_files_string(entries), "a.ts, b.ts")

    def test_build_review_completion_prompt(self):
        review_path = Path("/fake/review.md")
        prompt = build_review_completion_prompt(review_path)
        self.assertIn(str(review_path), prompt)
        self.assertIn("Return only the final markdown review to stdout.", prompt)
        self.assertIn("Do not output planning notes, progress updates, or next-step narration.", prompt)
        self.assertIn("non-Pending Verdict", prompt)

    def test_block_response_outputs_json(self):
        with patch("builtins.print") as mock_print:
            block_response("msg", "feedback")
        self.assertEqual(mock_print.call_count, 2)
        payload = mock_print.call_args_list[0].args[0]
        parsed = json.loads(payload)
        self.assertEqual(parsed["decision"], "block")
        self.assertEqual(parsed["reason"], "feedback")
        self.assertEqual(parsed["systemMessage"], "msg")

    def test_build_review_findings_feedback_includes_review_content(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            review_path = Path(temp_dir) / "review.md"
            review_path.write_text("## Findings\nBug here\n\n## Verdict\n1 issue found.", encoding="utf-8")

            feedback = build_review_findings_feedback("rev1", review_path)

            self.assertIn("Act on the review below before stopping", feedback)
            self.assertIn("Fix each blocking Confirmed finding", feedback)
            self.assertIn("Bug here", feedback)
            self.assertIn(str(review_path), feedback)

    def test_build_review_findings_feedback_describes_threshold(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            review_path = Path(temp_dir) / "review.md"
            review_path.write_text("## Findings\nBug here\n\n## Verdict\n1 issue found.", encoding="utf-8")

            feedback = build_review_findings_feedback(
                "rev1",
                review_path,
                minimum_blocking_severity="high",
            )

            self.assertIn("Confirmed findings at High severity or higher block stopping.", feedback)
            self.assertIn("Lower-severity Confirmed findings are advisory", feedback)

    def test_review_feedback_max_chars_uses_settings(self):
        self.assertEqual(
            review_feedback_max_chars(PluginSettings.from_mapping({"reviewFeedbackMaxChars": "42"})),
            42,
        )

    def test_review_feedback_max_chars_falls_back_for_invalid_value(self):
        self.assertEqual(
            review_feedback_max_chars(PluginSettings.from_mapping({"reviewFeedbackMaxChars": "nope"})),
            9000,
        )

    def test_build_review_findings_feedback_truncates_to_configured_limit(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            review_path = Path(temp_dir) / "review.md"
            review_path.write_text("abcdef", encoding="utf-8")

            feedback = build_review_findings_feedback("rev1", review_path, max_chars=3)

            self.assertIn("abc", feedback)
            self.assertNotIn("def", feedback)
