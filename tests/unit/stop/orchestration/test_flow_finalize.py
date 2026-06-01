import unittest
from types import SimpleNamespace

from tests.support_paths import FAKE_ROOT

from claude_auto_review.state.models import ReviewMetadata
from unittest.mock import patch

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.state.models import EditRecord
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.flow import run_stop_flow
from claude_auto_review.stop.orchestration.resolution import ReviewResolution, TerminalResolution

_STATE = [EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1", reviewed=False)]


def _snapshot(*, events=_STATE):
    return StateSnapshot.from_events(events)


def _ctx(**overrides):
    return RuntimeContext(
        project_root=overrides.get("project_root", FAKE_ROOT),
        client_id=overrides.get("client_id", "sid"),
        settings=overrides.get(
            "settings",
            PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=5),
        ),
        payload=overrides.get("payload", {}),
    )


class TestFlowFinalize(unittest.TestCase):
    @patch("claude_auto_review.stop.orchestration.deps.log_event")
    @patch("claude_auto_review.stop.orchestration.deps.load_state_snapshot", return_value=_snapshot())
    def test_disabled_setting_returns_0_and_logs_stop_disabled(
        self,
        mock_state,
        mock_log,
    ):
        result = run_stop_flow(_ctx(settings=PluginSettings(enabled=False, pending_review_timeout_hours=1, max_stop_passes=5)))

        self.assertEqual(result, 0)
        mock_log.assert_called_once_with(FAKE_ROOT, "stop_disabled", client_id="sid")

    @patch("claude_auto_review.stop.orchestration.deps.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.deps.finalize_review_stop", return_value=2)
    @patch("claude_auto_review.stop.orchestration.deps.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.deps.load_state_snapshot", return_value=_snapshot())
    def test_non_terminal_resolution_is_forwarded_to_finalize(
        self,
        mock_state,
        mock_resolve,
        mock_finalize,
        mock_classify,
    ):
        mock_classify.return_value = SimpleNamespace(status="complete", reason="parsed_label")
        mock_resolve.return_value = ReviewResolution(
            review=ReviewMetadata(reviewId="r1", timestamp="2026-01-01T00:00:00+00:00", reviewPath="", files=[], clientId="sid"),
            state=[],
            unreviewed=_STATE,
        )

        result = run_stop_flow(
            _ctx(
                settings=PluginSettings(
                    enabled=True,
                    pending_review_timeout_hours=1,
                    max_stop_passes=5,
                    last_assistant_message_classifier_enabled=True,
                ),
                payload={"session_id": "sid", "last_assistant_message": "done"},
            )
        )

        self.assertEqual(result, 2)
        mock_finalize.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.deps.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.deps.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.deps.load_state_snapshot", return_value=_snapshot())
    def test_invalid_numeric_settings_fall_back_to_defaults(
        self,
        mock_state,
        mock_resolve,
        mock_classify,
    ):
        mock_classify.return_value = None
        mock_resolve.return_value = TerminalResolution(exit_code=2)

        settings = PluginSettings.from_mapping(
            {
                "enabled": True,
                "pendingReviewTimeoutHours": "not-a-number",
                "maxStopPasses": "also-bad",
            }
        )

        result = run_stop_flow(_ctx(settings=settings))

        self.assertEqual(result, 2)
        self.assertEqual(mock_resolve.call_args.args[3], 1.0)


if __name__ == "__main__":
    unittest.main()
