import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.support_paths import FAKE_ROOT

from claude_auto_review.config.settings.models import CoreSettings, FlowSettings, PluginSettings
from claude_auto_review.stop.orchestration.types.context import RuntimeContext
from claude_auto_review.stop.orchestration.deps import (
    ReviewEvalDeps,
    ReviewClassifierDeps,
    ReviewPlannerDeps,
    ReviewExecutorDeps,
    AutocompleteDeps,
)
from claude_auto_review.stop.orchestration.finalize.eval import orchestrate_review_eval
from claude_auto_review.stop.orchestration.finalize.outcomes import FinalizeEffect, FinalizePlan, approved_result
from claude_auto_review.stop.reviews.types.enums import AutocompleteStatus


def _ctx(**kwargs):
    return RuntimeContext(
        project_root=kwargs.get("project_root", FAKE_ROOT),
        client_id=kwargs.get("client_id", "sid"),
        settings=kwargs.get(
            "settings", PluginSettings(core=CoreSettings(enabled=True), flow=FlowSettings(pending_review_timeout_hours=1, max_stop_passes=5))
        ),
        payload=kwargs.get("payload", {}),
    )


def _mock_eval_deps(*, classify_fn=None, plan_fn=None, apply_fn=None, autocomplete_fn=None, log_event_fn=None):
    return ReviewEvalDeps(
        classifier=ReviewClassifierDeps(
            classify_fn=classify_fn or MagicMock(),
        ),
        planner=ReviewPlannerDeps(
            plan_for_artifact_state_fn=plan_fn or MagicMock(),
        ),
        executor=ReviewExecutorDeps(
            apply_plan_fn=apply_fn or MagicMock(),
            state_event_writer_factory=lambda p, c: MagicMock(),
            emitter=MagicMock(),
        ),
        autocomplete=AutocompleteDeps(
            attempt_autocomplete_fn=autocomplete_fn or MagicMock(),
            log_event_fn=log_event_fn if log_event_fn is not None else MagicMock(),
        ),
    )


class TestEvaluateArtifactAndPlan(unittest.TestCase):
    def _make_artifact_state(self, status_name):
        return SimpleNamespace(status=SimpleNamespace(value=status_name))

    def test_terminal_plan_found_on_first_classification(self):
        artifact_state = self._make_artifact_state("complete_clean")
        classify_fn = MagicMock(return_value=artifact_state)
        plan_fn = MagicMock(return_value=FinalizePlan(result=approved_result(), effect=FinalizeEffect.APPLY_COMPLETED_CLEAN_REVIEW))
        apply_fn = MagicMock(return_value=("result", None))

        deps = _mock_eval_deps(classify_fn=classify_fn, plan_fn=plan_fn, apply_fn=apply_fn)
        result = orchestrate_review_eval(
            _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
            deps=deps,
        )
        self.assertEqual(result, ("result", None))
        apply_fn.assert_called_once()
        self.assertEqual(classify_fn.call_count, 1)


    def test_autocomplete_then_plan_found(self):
        pending_state = self._make_artifact_state("pending")
        clean_state = self._make_artifact_state("complete_clean")
        classify_fn = MagicMock(side_effect=[pending_state, clean_state])
        plan_fn = MagicMock(side_effect=[None, SimpleNamespace(effect="apply")])
        apply_fn = MagicMock(return_value=("result", None))
        autocomplete_fn = MagicMock(return_value=SimpleNamespace(status="completed"))

        deps = _mock_eval_deps(
            classify_fn=classify_fn, plan_fn=plan_fn,
            apply_fn=apply_fn, autocomplete_fn=autocomplete_fn,
        )
        result = orchestrate_review_eval(
            _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
            deps=deps,
        )
        self.assertEqual(result, ("result", None))
        self.assertEqual(classify_fn.call_count, 2)
        autocomplete_fn.assert_called_once()

    def test_still_pending_after_autocomplete_returns_none(self):
        pending_state = self._make_artifact_state("pending")
        classify_fn = MagicMock(return_value=pending_state)
        plan_fn = MagicMock(return_value=None)
        autocomplete_fn = MagicMock(return_value=SimpleNamespace(status="completed"))

        deps = _mock_eval_deps(
            classify_fn=classify_fn, plan_fn=plan_fn, autocomplete_fn=autocomplete_fn,
        )
        result = orchestrate_review_eval(
            _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
            deps=deps,
        )
        self.assertIsNone(result)

    def test_empty_stdout_autocomplete_logs_event(self):
        pending_state = self._make_artifact_state("pending")
        classify_fn = MagicMock(return_value=pending_state)
        plan_fn = MagicMock(return_value=None)
        autocomplete_fn = MagicMock(return_value=SimpleNamespace(status=AutocompleteStatus.EMPTY_STDOUT))
        log_fn = MagicMock()

        deps = _mock_eval_deps(
            classify_fn=classify_fn, plan_fn=plan_fn,
            autocomplete_fn=autocomplete_fn, log_event_fn=log_fn,
        )
        result = orchestrate_review_eval(
            _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
            deps=deps,
        )
        self.assertIsNone(result)
        log_fn.assert_called_once()
        self.assertEqual(log_fn.call_args[0][1], "stop_hook_reviewer_empty_blocked")

    def test_non_empty_stdout_autocomplete_does_not_log(self):
        pending_state = self._make_artifact_state("pending")
        classify_fn = MagicMock(return_value=pending_state)
        plan_fn = MagicMock(return_value=None)
        autocomplete_fn = MagicMock(return_value=SimpleNamespace(status=AutocompleteStatus.OUTPUT_WRITTEN))
        log_fn = MagicMock()

        deps = _mock_eval_deps(
            classify_fn=classify_fn, plan_fn=plan_fn,
            autocomplete_fn=autocomplete_fn, log_event_fn=log_fn,
        )
        result = orchestrate_review_eval(
            _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
            deps=deps,
        )
        self.assertIsNone(result)
        log_fn.assert_not_called()

    def test_empty_stdout_followed_by_plan_does_not_log(self):
        pending_state = self._make_artifact_state("pending")
        clean_state = self._make_artifact_state("complete_clean")
        classify_fn = MagicMock(side_effect=[pending_state, clean_state])
        plan_fn = MagicMock(side_effect=[None, FinalizePlan(result=approved_result(), effect=FinalizeEffect.APPLY_COMPLETED_CLEAN_REVIEW)])
        apply_fn = MagicMock(return_value=("result", None))
        autocomplete_fn = MagicMock(return_value=SimpleNamespace(status=AutocompleteStatus.EMPTY_STDOUT))
        log_fn = MagicMock()

        deps = _mock_eval_deps(
            classify_fn=classify_fn,
            plan_fn=plan_fn,
            apply_fn=apply_fn,
            autocomplete_fn=autocomplete_fn,
            log_event_fn=log_fn,
        )
        result = orchestrate_review_eval(
            _ctx(), "r1", Path("/review.md"), Path("/prompt.md"), [], [],
            deps=deps,
        )
        self.assertEqual(result, ("result", None))
        log_fn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
