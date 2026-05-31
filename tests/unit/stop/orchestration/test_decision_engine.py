import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.decision_engine import StopDecisionEngine
from claude_auto_review.stop.orchestration.resolution import (
    StopDecisionKind,
    TerminalResolution,
)


def _ctx(**kwargs):
    return RuntimeContext(
        project_root=kwargs.get("project_root", Path("/fake")),
        client_id=kwargs.get("client_id", "sid"),
        settings=kwargs.get(
            "settings", PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=5)
        ),
        payload=kwargs.get("payload", {}),
    )


class TestStopDecisionEngine(unittest.TestCase):
    def test_evaluate_delegates_to_service(self):
        engine = StopDecisionEngine(_ctx())
        expected = MagicMock(kind=StopDecisionKind.TERMINAL)
        engine._service = MagicMock()
        engine._service.evaluate.return_value = expected
        result = engine.evaluate()
        self.assertIs(result, expected)

    def test_finalize_delegates_to_finalize_fn(self):
        finalize_fn = MagicMock(return_value=2)
        resolution = TerminalResolution(exit_code=2)
        engine = StopDecisionEngine(_ctx(), finalize_review_stop_fn=finalize_fn)
        result = engine.finalize(resolution)
        self.assertEqual(result, 2)
        finalize_fn.assert_called_once()

    def test_finalize_uses_provided_emitter(self):
        finalize_fn = MagicMock(return_value=0)
        emitter = MagicMock()
        engine = StopDecisionEngine(_ctx(), finalize_review_stop_fn=finalize_fn, emitter=emitter)
        engine.finalize(TerminalResolution(exit_code=0), emitter=emitter)
        _, kwargs = finalize_fn.call_args
        self.assertIs(kwargs["emitter"], emitter)

    def test_finalize_uses_default_emitter_when_none(self):
        finalize_fn = MagicMock(return_value=0)
        engine = StopDecisionEngine(_ctx(), finalize_review_stop_fn=finalize_fn)
        engine.finalize(TerminalResolution(exit_code=0))
        _, kwargs = finalize_fn.call_args
        self.assertIs(kwargs["emitter"], engine._emitter)

    @patch("claude_auto_review.stop.orchestration.decision_engine.StdoutResponseEmitter")
    def test_default_emitter_created_when_none(self, MockEmitter):
        engine = StopDecisionEngine(_ctx())
        MockEmitter.assert_called()

    def test_service_property(self):
        engine = StopDecisionEngine(_ctx())
        self.assertIsNotNone(engine.service)


if __name__ == "__main__":
    unittest.main()
