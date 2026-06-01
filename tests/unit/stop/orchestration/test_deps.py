import unittest
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.deps import (
    AutocompleteDeps,
    ReviewClassifierDeps,
    ReviewEvalDeps,
    ReviewExecutorDeps,
    ReviewPlannerDeps,
    StopFlowDependencies,
    build_default_dependencies,
    build_default_eval_deps,
)


class TestBuildDefaultDependencies(unittest.TestCase):
    def test_returns_dependencies(self):
        deps = build_default_dependencies()
        self.assertIsInstance(deps, StopFlowDependencies)

    def test_override_load_state_snapshot(self):
        fn = MagicMock()
        deps = build_default_dependencies(load_state_snapshot_fn=fn)
        self.assertIs(deps.state.load_state_snapshot, fn)

    def test_override_get_unreviewed_files(self):
        fn = MagicMock()
        deps = build_default_dependencies(get_unreviewed_files_fn=fn)
        self.assertIs(deps.state.get_unreviewed_files, fn)

    def test_override_consecutive_stop_blocks(self):
        fn = MagicMock()
        deps = build_default_dependencies(consecutive_stop_blocks_fn=fn)
        self.assertIs(deps.state.consecutive_stop_blocks, fn)

    def test_override_classify_last_assistant_message(self):
        fn = MagicMock()
        deps = build_default_dependencies(classify_last_assistant_message_fn=fn)
        self.assertIs(deps.classifier.classify_last_assistant_message, fn)

    def test_override_classifier_persist_factory(self):
        fn = MagicMock()
        deps = build_default_dependencies(classifier_persist_factory=fn)
        self.assertIs(deps.classifier.classifier_persist_factory, fn)

    def test_default_classifier_persist_factory(self):
        deps = build_default_dependencies()
        self.assertTrue(callable(deps.classifier.classifier_persist_factory))

    def test_override_resolve_pending_review(self):
        fn = MagicMock()
        deps = build_default_dependencies(resolve_pending_review_fn=fn)
        self.assertIs(deps.review.resolve_pending_review, fn)

    def test_override_get_reviewer_prompt_script(self):
        fn = MagicMock()
        deps = build_default_dependencies(get_reviewer_prompt_script_fn=fn)
        self.assertIs(deps.review.get_reviewer_prompt_script, fn)

    def test_override_log_event(self):
        fn = MagicMock()
        deps = build_default_dependencies(log_event_fn=fn)
        self.assertIs(deps.log_event, fn)

    def test_override_emitter(self):
        emitter = MagicMock()
        deps = build_default_dependencies(emitter=emitter)
        self.assertIs(deps.emitter, emitter)

    def test_override_finalize_review_stop(self):
        fn = MagicMock()
        deps = build_default_dependencies(finalize_review_stop_fn=fn)
        self.assertIs(deps.finalize_review_stop, fn)


class TestBuildDefaultEvalDeps(unittest.TestCase):
    def test_returns_review_eval_deps(self):
        deps = build_default_eval_deps()
        self.assertIsInstance(deps, ReviewEvalDeps)

    def test_override_classify_fn(self):
        fn = MagicMock()
        deps = build_default_eval_deps(classify_fn=fn)
        self.assertIs(deps.classifier.classify_fn, fn)

    def test_override_plan_for_artifact_state_fn(self):
        fn = MagicMock()
        deps = build_default_eval_deps(plan_for_artifact_state_fn=fn)
        self.assertIs(deps.planner.plan_for_artifact_state_fn, fn)

    def test_override_apply_plan_fn(self):
        fn = MagicMock()
        deps = build_default_eval_deps(apply_plan_fn=fn)
        self.assertIs(deps.executor.apply_plan_fn, fn)

    def test_override_attempt_autocomplete_fn(self):
        fn = MagicMock()
        deps = build_default_eval_deps(attempt_autocomplete_fn=fn)
        self.assertIs(deps.autocomplete.attempt_autocomplete_fn, fn)

    def test_override_state_event_writer_factory(self):
        fn = MagicMock()
        deps = build_default_eval_deps(state_event_writer_factory=fn)
        self.assertIs(deps.executor.state_event_writer_factory, fn)

    @patch("claude_auto_review.stop.orchestration.deps._ConcreteStateEventWriter")
    def test_default_state_event_writer_factory(self, writer_cls):
        deps = build_default_eval_deps()
        self.assertTrue(callable(deps.executor.state_event_writer_factory))
        self.assertIs(deps.executor.state_event_writer_factory, writer_cls)


if __name__ == "__main__":
    unittest.main()
