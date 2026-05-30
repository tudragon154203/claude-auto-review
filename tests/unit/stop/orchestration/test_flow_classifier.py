import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.state.models import EditRecord, StopBlockedRecord
from claude_auto_review.state.snapshot import StateSnapshot
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.flow import run_stop_flow
from claude_auto_review.stop.orchestration.resolution import TerminalResolution

_UNREVIEWED = [EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1")]
_STATE = [EditRecord(timestamp="2026-05-11T10:00:00+07:00", file="a.ts", hash="1", reviewed=False)]


def _snapshot(*, events=_STATE):
    return StateSnapshot.from_events(events)


def _ctx(**overrides):
    return RuntimeContext(
        project_root=overrides.get("project_root", Path("/fake")),
        client_id=overrides.get("client_id", "sid"),
        settings=overrides.get(
            "settings",
            PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=5),
        ),
        payload=overrides.get("payload", {}),
    )


class TestFlowClassifier(unittest.TestCase):
    @patch("claude_auto_review.stop.orchestration.deps.classify_last_assistant_message")
    @patch(
        "claude_auto_review.stop.orchestration.deps.load_state_snapshot", return_value=_snapshot(events=[])
    )
    def test_classifier_skipped_when_no_unreviewed_files(
        self,
        mock_state,
        mock_classify,
    ):
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

        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.deps.classify_last_assistant_message")
    @patch(
        "claude_auto_review.stop.orchestration.deps.load_state_snapshot",
        return_value=_snapshot(
            events=[
                EditRecord(timestamp="2026-05-11T09:00:00+07:00", file="a.ts", hash="1", reviewed=True),
                StopBlockedRecord(timestamp="2026-05-11T10:00:00+07:00"),
                StopBlockedRecord(timestamp="2026-05-11T10:01:00+07:00"),
                StopBlockedRecord(timestamp="2026-05-11T10:02:00+07:00"),
                StopBlockedRecord(timestamp="2026-05-11T10:03:00+07:00"),
                StopBlockedRecord(timestamp="2026-05-11T10:04:00+07:00"),
                EditRecord(timestamp="2026-05-11T10:05:00+07:00", file="a.ts", hash="2", reviewed=False),
            ]
        ),
    )
    def test_classifier_skipped_when_circuit_breaker_allows_stop(
        self,
        mock_state,
        mock_classify,
    ):
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

        self.assertEqual(result, 0)
        mock_classify.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.deps.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.deps.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.deps.load_state_snapshot", return_value=_snapshot())
    def test_classifier_invoked_when_enabled(
        self,
        mock_state,
        mock_resolve,
        mock_classify,
    ):
        mock_classify.return_value = SimpleNamespace(status="complete", reason="parsed_label")
        mock_resolve.return_value = TerminalResolution(exit_code=0)

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

        self.assertEqual(result, 0)
        mock_classify.assert_called_once()

    @patch("claude_auto_review.stop.orchestration.deps.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.deps.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.deps.load_state_snapshot", return_value=_snapshot())
    def test_classifier_incomplete_allows_stop_before_review_resolution(
        self,
        mock_state,
        mock_resolve,
        mock_classify,
    ):
        mock_classify.return_value = SimpleNamespace(status="incomplete", reason="parsed_label")

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

        self.assertEqual(result, 0)
        mock_resolve.assert_not_called()

    @patch("claude_auto_review.stop.orchestration.deps.classify_last_assistant_message")
    @patch("claude_auto_review.stop.orchestration.deps.resolve_pending_review")
    @patch("claude_auto_review.stop.orchestration.deps.load_state_snapshot", return_value=_snapshot())
    def test_disabled_setting_bypasses_classifier_without_changing_result(
        self,
        mock_state,
        mock_resolve,
        mock_classify,
    ):
        mock_resolve.return_value = TerminalResolution(exit_code=2)

        result = run_stop_flow(
            _ctx(
                settings=PluginSettings(
                    enabled=True,
                    pending_review_timeout_hours=1,
                    max_stop_passes=5,
                    last_assistant_message_classifier_enabled=False,
                ),
                payload={"session_id": "sid", "last_assistant_message": "done"},
            )
        )

        self.assertEqual(result, 2)
        mock_classify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
