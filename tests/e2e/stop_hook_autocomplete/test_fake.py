from tests.e2e.stop_hook_autocomplete.support import StopHookAutocompleteTestCase


class EndToEndStopHookAutocompleteFakeTests(StopHookAutocompleteTestCase):
    def test_stop_hook_auto_completes_review_with_fake_claude(self):
        project_root = self.temp_project()
        self.create_tracked_app(project_root)

        stop = self.stop(project_root)
        self.assert_stop_approved(stop)
        self.assert_review_completed(project_root, "Clean - no issues found. Claude may stop.")
        self.assert_fake_claude_run(project_root)
        self.assert_state_fully_reviewed(project_root)

    def test_stop_hook_auto_completes_review_with_fake_codex(self):
        project_root = self.temp_project()
        self.configure_codex_backend(project_root)
        self.create_tracked_app(project_root)

        stop = self.stop(project_root, use_fake_claude=False, use_fake_codex=True)
        self.assert_stop_approved(stop)
        self.assert_review_completed(project_root, "Clean - no issues found. Claude may stop.")
        self.assert_fake_codex_run(project_root)
        self.assert_state_fully_reviewed(project_root)
