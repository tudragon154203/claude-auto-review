import unittest
from unittest.mock import MagicMock

from claude_auto_review.stop.orchestration.deps import (
    AutocompleteDeps,
    DependencyOverrides,
    ReviewClassifierDeps,
    ReviewEvalDeps,
    ReviewExecutorDeps,
    ReviewPlannerDeps,
    StopFlowDependencies,
    build_default_dependencies,
    build_default_eval_deps,
)


def _mock_emitter():
    return MagicMock()


class TestBuildDefaultDependencies(unittest.TestCase):
    def test_returns_dependencies(self):
        deps = build_default_dependencies(DependencyOverrides(), emitter=_mock_emitter())
        self.assertIsInstance(deps, StopFlowDependencies)

    def test_override_load_state_snapshot(self):
        fn = MagicMock()
        deps = build_default_dependencies(DependencyOverrides(load_state_snapshot_fn=fn), emitter=_mock_emitter())
        self.assertIs(deps.state.load_state_snapshot, fn)

    def test_override_get_unreviewed_files(self):
        fn = MagicMock()
        deps = build_default_dependencies(DependencyOverrides(get_unreviewed_files_fn=fn), emitter=_mock_emitter())
        self.assertIs(deps.state.get_unreviewed_files, fn)

    def test_override_consecutive_stop_blocks(self):
        fn = MagicMock()
        deps = build_default_dependencies(DependencyOverrides(consecutive_stop_blocks_fn=fn), emitter=_mock_emitter())
        self.assertIs(deps.state.consecutive_stop_blocks, fn)

    def test_override_classify_last_assistant_message(self):
        fn = MagicMock()
        deps = build_default_dependencies(DependencyOverrides(classify_last_assistant_message_fn=fn), emitter=_mock_emitter())
        self.assertIs(deps.classifier.classify_last_assistant_message, fn)

    def test_override_classifier_persist_factory(self):
        fn = MagicMock()
        deps = build_default_dependencies(DependencyOverrides(classifier_persist_factory=fn), emitter=_mock_emitter())
        self.assertIs(deps.classifier.classifier_persist_factory, fn)

    def test_default_classifier_persist_factory(self):
        deps = build_default_dependencies(DependencyOverrides(), emitter=_mock_emitter())
        self.assertTrue(callable(deps.classifier.classifier_persist_factory))

    def test_override_resolve_pending_review(self):
        fn = MagicMock()
        deps = build_default_dependencies(DependencyOverrides(resolve_pending_review_fn=fn), emitter=_mock_emitter())
        self.assertIs(deps.review.resolve_pending_review, fn)

    def test_override_get_reviewer_prompt_script(self):
        fn = MagicMock()
        deps = build_default_dependencies(DependencyOverrides(get_reviewer_prompt_script_fn=fn), emitter=_mock_emitter())
        self.assertIs(deps.review.get_reviewer_prompt_script, fn)

    def test_override_log_event(self):
        fn = MagicMock()
        deps = build_default_dependencies(DependencyOverrides(log_event_fn=fn), emitter=_mock_emitter())
        self.assertIs(deps.log_event, fn)

    def test_override_emitter(self):
        emitter = MagicMock()
        deps = build_default_dependencies(DependencyOverrides(), emitter=emitter)
        self.assertIs(deps.emitter, emitter)

    def test_override_finalize_review_stop(self):
        fn = MagicMock()
        deps = build_default_dependencies(DependencyOverrides(finalize_review_stop_fn=fn), emitter=_mock_emitter())
        self.assertIs(deps.finalize_review_stop, fn)


class TestBuildDefaultEvalDeps(unittest.TestCase):
    def test_returns_review_eval_deps(self):
        deps = build_default_eval_deps(DependencyOverrides(state_event_writer_factory=MagicMock()), emitter=_mock_emitter())
        self.assertIsInstance(deps, ReviewEvalDeps)

    def test_override_classify_fn(self):
        fn = MagicMock()
        deps = build_default_eval_deps(DependencyOverrides(eval_classify_fn=fn, state_event_writer_factory=MagicMock()), emitter=_mock_emitter())
        self.assertIs(deps.classifier.classify_fn, fn)

    def test_override_plan_for_artifact_state_fn(self):
        fn = MagicMock()
        deps = build_default_eval_deps(DependencyOverrides(eval_plan_fn=fn, state_event_writer_factory=MagicMock()), emitter=_mock_emitter())
        self.assertIs(deps.planner.plan_for_artifact_state_fn, fn)

    def test_override_apply_plan_fn(self):
        fn = MagicMock()
        deps = build_default_eval_deps(DependencyOverrides(eval_apply_fn=fn, state_event_writer_factory=MagicMock()), emitter=_mock_emitter())
        self.assertIs(deps.executor.apply_plan_fn, fn)

    def test_override_attempt_autocomplete_fn(self):
        fn = MagicMock()
        deps = build_default_eval_deps(DependencyOverrides(eval_attempt_fn=fn, state_event_writer_factory=MagicMock()), emitter=_mock_emitter())
        self.assertIs(deps.autocomplete.attempt_autocomplete_fn, fn)

    def test_override_state_event_writer_factory(self):
        fn = MagicMock()
        deps = build_default_eval_deps(DependencyOverrides(state_event_writer_factory=fn), emitter=_mock_emitter())
        self.assertIs(deps.executor.state_event_writer_factory, fn)

    def test_emitter_passed_to_executor(self):
        emitter = MagicMock()
        deps = build_default_eval_deps(DependencyOverrides(state_event_writer_factory=MagicMock()), emitter=emitter)
        self.assertIs(deps.executor.emitter, emitter)

    def test_log_event_fn_passed_to_autocomplete(self):
        fn = MagicMock()
        deps = build_default_eval_deps(DependencyOverrides(log_event_fn=fn, state_event_writer_factory=MagicMock()), emitter=_mock_emitter())
        self.assertIs(deps.autocomplete.log_event_fn, fn)


if __name__ == "__main__":
    unittest.main()
