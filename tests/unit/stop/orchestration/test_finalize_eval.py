import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.support_paths import FAKE_ROOT

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.orchestration.finalize_eval import evaluate_artifact_and_plan


def _ctx(**kwargs):
    return RuntimeContext(
        project_root=kwargs.get("project_root", FAKE_ROOT),
        client_id=kwargs.get("client_id", "sid"),
        settings=kwargs.get(
            "settings", PluginSettings(enabled=True, pending_review_timeout_hours=1, max_stop_passes=5)
        ),
        payload=kwargs.get("payload", {}),
    )


class TestEvaluateArtifactAndPlan(unittest.TestCase):
    def _make_artifact_state(self, status_name):
        return SimpleNamespace(status=SimpleNamespace(value=status_name))

    def test_plan_found_on_first_classification(self):
        artifact_state = self._make_artifact_state("complete_clean")
        classify_fn = MagicMock(return_value=artifact_state)
        plan_fn = MagicMock(return_value=SimpleNamespace(effect="apply"))
        apply_fn = MagicMock(return_value=("result", None))

        result = evaluate_artifact_and_plan(
            _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
            classify_fn=classify_fn, plan_for_artifact_state_fn=plan_fn, apply_plan_fn=apply_fn,
        )
        self.assertEqual(result, ("result", None))
        apply_fn.assert_called_once()
        # Should not attempt autocomplete
        self.assertEqual(classify_fn.call_count, 1)

    def test_autocomplete_then_plan_found(self):
        pending_state = self._make_artifact_state("pending")
        clean_state = self._make_artifact_state("complete_clean")
        classify_fn = MagicMock(side_effect=[pending_state, clean_state])
        plan_fn = MagicMock(side_effect=[None, SimpleNamespace(effect="apply")])
        apply_fn = MagicMock(return_value=("result", None))
        autocomplete_fn = MagicMock(return_value=SimpleNamespace(status="completed"))

        result = evaluate_artifact_and_plan(
            _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
            classify_fn=classify_fn, plan_for_artifact_state_fn=plan_fn,
            apply_plan_fn=apply_fn, attempt_autocomplete_fn=autocomplete_fn,
        )
        self.assertEqual(result, ("result", None))
        self.assertEqual(classify_fn.call_count, 2)
        autocomplete_fn.assert_called_once()

    def test_still_pending_after_autocomplete_returns_none(self):
        pending_state = self._make_artifact_state("pending")
        classify_fn = MagicMock(return_value=pending_state)
        plan_fn = MagicMock(return_value=None)
        autocomplete_fn = MagicMock(return_value=SimpleNamespace(status="completed"))

        result = evaluate_artifact_and_plan(
            _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
            classify_fn=classify_fn, plan_for_artifact_state_fn=plan_fn,
            apply_plan_fn=MagicMock(), attempt_autocomplete_fn=autocomplete_fn,
        )
        self.assertIsNone(result)

    def test_empty_stdout_autocomplete_logs_event(self):
        pending_state = self._make_artifact_state("pending")
        classify_fn = MagicMock(return_value=pending_state)
        plan_fn = MagicMock(return_value=None)
        autocomplete_fn = MagicMock(return_value=SimpleNamespace(status="empty_stdout"))
        log_fn = MagicMock()

        with unittest.mock.patch("claude_auto_review.stop.orchestration.finalize_eval.log_event", log_fn):
            result = evaluate_artifact_and_plan(
                _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
                classify_fn=classify_fn, plan_for_artifact_state_fn=plan_fn,
                apply_plan_fn=MagicMock(), attempt_autocomplete_fn=autocomplete_fn,
            )
        self.assertIsNone(result)
        log_fn.assert_called_once()
        self.assertEqual(log_fn.call_args[0][1], "stop_hook_reviewer_empty_blocked")

    def test_non_empty_stdout_autocomplete_does_not_log(self):
        pending_state = self._make_artifact_state("pending")
        classify_fn = MagicMock(return_value=pending_state)
        plan_fn = MagicMock(return_value=None)
        autocomplete_fn = MagicMock(return_value=SimpleNamespace(status="completed"))
        log_fn = MagicMock()

        with unittest.mock.patch("claude_auto_review.stop.orchestration.finalize_eval.log_event", log_fn):
            result = evaluate_artifact_and_plan(
                _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
                classify_fn=classify_fn, plan_for_artifact_state_fn=plan_fn,
                apply_plan_fn=MagicMock(), attempt_autocomplete_fn=autocomplete_fn,
            )
        self.assertIsNone(result)
        log_fn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
