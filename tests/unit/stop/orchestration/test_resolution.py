import unittest

from claude_auto_review.stop.orchestration.resolution import (
    ReviewResolution,
    StopFlowResolution,
    TerminalResolution,
)


class TestStopFlowResolution(unittest.TestCase):
    def test_terminal_is_terminal(self):
        r = TerminalResolution(exit_code=2)
        self.assertTrue(isinstance(r, StopFlowResolution))
        self.assertEqual(r.exit_code, 2)

    def test_review_resolution_not_terminal(self):
        r = ReviewResolution(state=[], unreviewed=[], review={"reviewId": "r1"})
        self.assertTrue(isinstance(r, StopFlowResolution))
        self.assertEqual(r.review["reviewId"], "r1")
