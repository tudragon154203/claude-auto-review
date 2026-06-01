import unittest
from unittest.mock import MagicMock, patch

from tests.support_paths import FAKE_ROOT
from claude_auto_review.config.models import PluginSettings
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.decision_engine import StopDecisionEngine
from claude_auto_review.stop.orchestration.resolution import StopDecisionKind, TerminalResolution


def _ctx(**kwargs):
    return RuntimeContext(
        project_root=kwargs.get("project_root", FAKE_ROOT),
        client_id=kwargs.get("client_id", "c1"),
        settings=kwargs.get(
            "settings",
            PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=5),
        ),
        payload=kwargs.get("payload", {}),
    )


class TestStopDecisionEngine(unittest.TestCase):
    def test_evaluate_delegates_to_service(self):
        engine = StopDecisionEngine(_ctx())
        expected = MagicMock(kind=StopDecisionKind.TERMINAL)
        engine._service.evaluate = MagicMock(return_value=expected)
        result = engine.evaluate()
        self.assertIs(result, expected)

    def test_finalize_delegates_to_finalize_fn(self):
        finalize_fn = MagicMock(return_value=2)
        resolution = TerminalResolution(exit_code=2)
        engine = StopDecisionEngine(_ctx(), finalize_review_stop_fn=finalize_fn)
        result = engine.finalize(resolution)
        self.assertEqual(result, 2)

    def test_finalize_passes_eval_deps(self):
        finalize_fn = MagicMock(return_value=0)
        engine = StopDecisionEngine(_ctx(), finalize_review_stop_fn=finalize_fn)
        engine.finalize(TerminalResolution(exit_code=0))
        _, kwargs = finalize_fn.call_args
        self.assertIs(kwargs["deps"], engine.eval_deps)

    def test_finalize_uses_default_emitter_when_none(self):
        finalize_fn = MagicMock(return_value=0)
        engine = StopDecisionEngine(_ctx(), finalize_review_stop_fn=finalize_fn)
        engine.finalize(TerminalResolution(exit_code=0))
        _, kwargs = finalize_fn.call_args
        self.assertIs(kwargs["deps"].emitter, engine.emitter)

    def test_finalize_uses_provided_emitter(self):
        finalize_fn = MagicMock(return_value=0)
        emitter = MagicMock()
        engine = StopDecisionEngine(_ctx(), finalize_review_stop_fn=finalize_fn, emitter=emitter)
        engine.finalize(TerminalResolution(exit_code=0))
        _, kwargs = finalize_fn.call_args
        self.assertIs(kwargs["deps"].emitter, emitter)

    def test_run_delegates_to_service(self):
        engine = StopDecisionEngine(_ctx())
        expected = MagicMock(kind=StopDecisionKind.TERMINAL)
        engine._service.run = MagicMock(return_value=expected)
        result = engine.run()
        self.assertIs(result, expected)

    @patch("claude_auto_review.stop.orchestration.decision_engine.build_default_eval_deps")
    def test_builds_eval_deps_with_engine_emitter(self, build_eval_deps):
        build_eval_deps.return_value = MagicMock()
        emitter = MagicMock()
        StopDecisionEngine(_ctx(), emitter=emitter)
        _, kwargs = build_eval_deps.call_args
        self.assertIs(kwargs["emitter"], emitter)


if __name__ == "__main__":
    unittest.main()
