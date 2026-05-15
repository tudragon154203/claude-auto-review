import unittest
from claude_auto_review.stop.orchestration.core.resolution import StopFlowResolution


class TestStopFlowResolution(unittest.TestCase):
    def test_is_terminal_when_exit_code_set(self):
        r = StopFlowResolution(state=[], unreviewed=[], exit_code=2)
        self.assertTrue(r.is_terminal)

    def test_is_not_terminal_when_no_exit_code(self):
        r = StopFlowResolution(state=[], unreviewed=[], review={"reviewId": "r1"})
        self.assertFalse(r.is_terminal)
