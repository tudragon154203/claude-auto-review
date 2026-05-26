import unittest
from types import SimpleNamespace
from unittest.mock import patch

from claude_auto_review.stop.orchestration.flow import _handle_allow, _handle_finalize, _handle_terminal


class TestFlowDispatch(unittest.TestCase):
    @patch("claude_auto_review.stop.orchestration.flow.approve_response")
    def test_handle_allow_approves_and_returns_zero(self, mock_approve):
        decision = SimpleNamespace(reason="disabled")
        result = _handle_allow(decision)
        self.assertEqual(result, 0)
        mock_approve.assert_called_once_with("Claude Auto Review: stop approved (disabled)")

    def test_handle_terminal_returns_exit_code(self):
        decision = SimpleNamespace(details={"exit_code": 2})
        self.assertEqual(_handle_terminal(decision), 2)

    def test_handle_finalize_forwards_resolution(self):
        engine = SimpleNamespace(finalize=lambda resolution: (3 if resolution == "r1" else 1))
        decision = SimpleNamespace(details={"resolution": "r1"})
        self.assertEqual(_handle_finalize(engine, decision), 3)


if __name__ == "__main__":
    unittest.main()
