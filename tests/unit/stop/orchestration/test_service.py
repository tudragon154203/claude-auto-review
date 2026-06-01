import unittest
from unittest.mock import MagicMock

from tests.support_paths import FAKE_ROOT
from claude_auto_review.config.models import PluginSettings
from claude_auto_review.state.edit_record import EditRecord
from claude_auto_review.state.review_records import ReviewMetadata
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.deps import (
    ClassifierDeps,
    ReviewDeps,
    StateDeps,
    StopFlowDependencies,
)
from claude_auto_review.stop.orchestration.resolution import ReviewResolution, StopDecisionKind, TerminalResolution
from claude_auto_review.stop.orchestration.service import StopFlowService


def _ctx(**kwargs):
    return RuntimeContext(
        project_root=kwargs.get("project_root", FAKE_ROOT),
        client_id=kwargs.get("client_id", "c1"),
        settings=kwargs.get(
            "settings",
            PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=5),
        ),
    )


def _snapshot(events=None):
    events = events or [
        EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1", reviewed=False)
    ]
    return StateSnapshot.from_events(events)


def _deps(**overrides):
    return StopFlowDependencies(
        state=overrides.get(
            "state",
            StateDeps(
                load_state_snapshot=MagicMock(return_value=_snapshot()),
                get_unreviewed_files=MagicMock(return_value=["u1"]),
                consecutive_stop_blocks=MagicMock(return_value=0),
            ),
        ),
        classifier=overrides.get(
            "classifier",
            ClassifierDeps(
                classify_last_assistant_message=MagicMock(return_value=None),
                classifier_persist_factory=MagicMock(return_value=MagicMock()),
            ),
        ),
        review=overrides.get(
            "review",
            ReviewDeps(
                resolve_pending_review=MagicMock(return_value=TerminalResolution(exit_code=2)),
                get_reviewer_prompt_script=MagicMock(return_value="reviewer.py"),
            ),
        ),
        log_event=overrides.get("log_event", MagicMock()),
        emitter=overrides.get("emitter", MagicMock()),
        finalize_review_stop=overrides.get("finalize_review_stop", MagicMock()),
    )


class TestStopFlowService(unittest.TestCase):
    def test_service_allows_when_disabled(self):
        service = StopFlowService(_ctx(settings=PluginSettings(enabled=False)), deps=_deps())
        decision = service.run()
        self.assertEqual(decision.kind, StopDecisionKind.ALLOW)
        self.assertEqual(decision.reason, "disabled")

    def test_service_returns_terminal_pending_resolution(self):
        service = StopFlowService(_ctx(), deps=_deps())
        decision = service.run()
        self.assertEqual(decision.kind, StopDecisionKind.TERMINAL)
        self.assertEqual(decision.details, {"exit_code": 2})

    def test_service_returns_finalize_resolution(self):
        resolution = ReviewResolution(
            review=ReviewMetadata(
                reviewId="r1",
                timestamp="2026-01-01T00:00:00+00:00",
                reviewPath="",
                files=[],
                clientId="c1",
            ),
            state=[],
            unreviewed=[],
        )
        review = ReviewDeps(
            resolve_pending_review=MagicMock(return_value=resolution),
            get_reviewer_prompt_script=MagicMock(return_value="reviewer.py"),
        )
        service = StopFlowService(_ctx(), deps=_deps(review=review))
        decision = service.run()
        self.assertEqual(decision.kind, StopDecisionKind.FINALIZE)
        self.assertIs(decision.details["resolution"], resolution)


if __name__ == "__main__":
    unittest.main()
