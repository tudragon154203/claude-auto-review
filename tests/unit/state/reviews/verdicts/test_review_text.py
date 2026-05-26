import tempfile
import unittest

from claude_auto_review.state.reviews.review_text import get_review_verdict_text


class TestGetReviewVerdictText(unittest.TestCase):

    def test_reads_verdict_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".md", delete=False, dir=tmpdir
            )
            try:
                review_path.write("## Findings\nNo issues.\n\n## Verdict\nClean.\n")
                review_path.flush()
                result = get_review_verdict_text(review_path.name)
                self.assertEqual(result, "Clean.")
            finally:
                review_path.close()
                import os
                os.unlink(review_path.name)

    def test_returns_none_for_nonexistent_file(self):
        result = get_review_verdict_text("/nonexistent/path/review.md")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()