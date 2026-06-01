import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from claude_auto_review.stop.orchestration.flow import _handle_allow, _handle_finalize, _handle_terminal
from claude_auto_review.stop.reviews.enums import StopAllowReason


class TestFlowDispatch(unittest.TestCase):
    def test_handle_allow_approves_and_returns_zero(self):
        emitter = MagicMock()
        engine = SimpleNamespace()
        decision = SimpleNamespace(reason=StopAllowReason.DISABLED)
        result = _handle_allow(engine, decision, emitter=emitter)
        self.assertEqual(result, 0)
        emitter.approve.assert_called_once_with("Claude Auto Review: stop approved (disabled)")

    def test_handle_terminal_returns_exit_code(self):
        engine = SimpleNamespace()
        decision = SimpleNamespace(details={"exit_code": 2})
        self.assertEqual(_handle_terminal(engine, decision, emitter=MagicMock()), 2)

    def test_handle_finalize_forwards_resolution(self):
        emitter = MagicMock()
        engine = SimpleNamespace(finalize=lambda resolution, **kwargs: (3 if resolution == "r1" else 1))
        decision = SimpleNamespace(details={"resolution": "r1"})
        self.assertEqual(_handle_finalize(engine, decision, emitter=emitter), 3)


if __name__ == "__main__":
    unittest.main()
