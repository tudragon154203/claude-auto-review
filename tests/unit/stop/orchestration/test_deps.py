import unittest
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.deps import (
    StopFlowDependencies,
    build_default_dependencies,
)


class TestBuildDefaultDependencies(unittest.TestCase):
    def test_returns_deps_and_finalize_fn(self):
        deps, finalize_fn = build_default_dependencies()
        self.assertIsInstance(deps, StopFlowDependencies)
        self.assertTrue(callable(finalize_fn))

    def test_override_load_state_snapshot(self):
        fn = MagicMock()
        deps, _ = build_default_dependencies(load_state_snapshot_fn=fn)
        self.assertIs(deps.state.load_state_snapshot, fn)

    def test_override_get_unreviewed_files(self):
        fn = MagicMock()
        deps, _ = build_default_dependencies(get_unreviewed_files_fn=fn)
        self.assertIs(deps.state.get_unreviewed_files, fn)

    def test_override_consecutive_stop_blocks(self):
        fn = MagicMock()
        deps, _ = build_default_dependencies(consecutive_stop_blocks_fn=fn)
        self.assertIs(deps.state.consecutive_stop_blocks, fn)

    def test_override_classify_last_assistant_message(self):
        fn = MagicMock()
        deps, _ = build_default_dependencies(classify_last_assistant_message_fn=fn)
        self.assertIs(deps.classifier.classify_last_assistant_message, fn)

    def test_override_resolve_pending_review(self):
        fn = MagicMock()
        deps, _ = build_default_dependencies(resolve_pending_review_fn=fn)
        self.assertIs(deps.review.resolve_pending_review, fn)

    def test_override_get_reviewer_prompt_script(self):
        fn = MagicMock()
        deps, _ = build_default_dependencies(get_reviewer_prompt_script_fn=fn)
        self.assertIs(deps.review.get_reviewer_prompt_script, fn)

    def test_override_log_event(self):
        fn = MagicMock()
        deps, _ = build_default_dependencies(log_event_fn=fn)
        self.assertIs(deps.log_event, fn)

    def test_override_finalize_review_stop(self):
        fn = MagicMock()
        _, finalize_fn = build_default_dependencies(finalize_review_stop_fn=fn)
        self.assertIs(finalize_fn, fn)

    def test_override_emitter(self):
        emitter = MagicMock()
        deps, _ = build_default_dependencies(emitter=emitter)
        self.assertIs(deps.emitter, emitter)

    @patch("claude_auto_review.stop.orchestration.deps.StdoutResponseEmitter")
    def test_default_emitter_when_none(self, MockEmitter):
        mock_instance = MagicMock()
        MockEmitter.return_value = mock_instance
        deps, _ = build_default_dependencies()
        self.assertIs(deps.emitter, mock_instance)


if __name__ == "__main__":
    unittest.main()
