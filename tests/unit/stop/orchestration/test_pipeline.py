import unittest
from pathlib import Path
from types import SimpleNamespace

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.state.models import EditRecord
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.pipeline import StopFlowDependencies, StopFlowPipeline
from claude_auto_review.stop.orchestration.resolution import StopDecisionKind


def _ctx(**kwargs):
    return RuntimeContext(
        project_root=kwargs.get("project_root", Path("/fake")),
        client_id=kwargs.get("client_id", "sid"),
        settings=kwargs.get("settings", PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=5)),
        payload=kwargs.get("payload", {}),
    )


def _snapshot(events=None):
    events = events or [EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1", reviewed=False)]
    return StateSnapshot.from_events(events)


def _deps(**overrides):
    base = StopFlowDependencies(
        load_state_snapshot=lambda *_args, **_kwargs: _snapshot(),
        get_unreviewed_files=lambda snapshot: snapshot.unreviewed_files,
        consecutive_stop_blocks=lambda _snapshot: 0,
        classify_last_assistant_message=lambda _ctx: None,
        resolve_pending_review=lambda *_args, **_kwargs: SimpleNamespace(is_terminal=True, exit_code=2),
        get_reviewer_prompt_script=lambda: "reviewer.py",
        log_event=lambda *_args, **_kwargs: None,
    )
    values = base.__dict__ | overrides
    return StopFlowDependencies(**values)


class TestStopFlowPipeline(unittest.TestCase):
    def test_pipeline_allows_when_disabled(self):
        pipeline = StopFlowPipeline(_ctx(settings=PluginSettings(enabled=False)), _deps())
        decision = pipeline.run()
        self.assertEqual(decision.kind, StopDecisionKind.ALLOW)
        self.assertEqual(decision.reason, "disabled")

    def test_pipeline_returns_terminal_pending_resolution(self):
        pipeline = StopFlowPipeline(_ctx(), _deps())
        decision = pipeline.run()
        self.assertEqual(decision.kind, StopDecisionKind.TERMINAL)
        self.assertEqual(decision.details, {"exit_code": 2})

    def test_pipeline_returns_finalize_resolution(self):
        resolution = SimpleNamespace(is_terminal=False, exit_code=None)
        pipeline = StopFlowPipeline(_ctx(), _deps(resolve_pending_review=lambda *_args, **_kwargs: resolution))
        decision = pipeline.run()
        self.assertEqual(decision.kind, StopDecisionKind.FINALIZE)
        self.assertIs(decision.details["resolution"], resolution)


if __name__ == "__main__":
    unittest.main()
