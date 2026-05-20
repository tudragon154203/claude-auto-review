import unittest

from tests.e2e.stop_hook_autocomplete.support import StopHookAutocompleteTestCase
from tests.support import real_claude_cli_available, real_codex_cli_available


class EndToEndStopHookAutocompleteRealTests(StopHookAutocompleteTestCase):
    @unittest.skipUnless(real_claude_cli_available(), "real claude CLI not available")
    def test_stop_hook_auto_completes_review_with_real_claude(self):
        project_root = self.temp_project()
        self.create_tracked_app(project_root)

        stop = self.stop(project_root, use_fake_claude=False)
        self.assert_stop_approved(stop)
        self.assert_review_completed(project_root)
        self.assert_reviewer_done_logged(project_root)

    @unittest.skipUnless(real_codex_cli_available(), "real codex CLI not available")
    def test_stop_hook_auto_completes_review_with_real_codex(self):
        project_root = self.temp_project()
        self.configure_codex_backend(project_root)
        self.create_tracked_app(project_root)

        stop = self.stop(project_root, use_fake_claude=False, use_fake_codex=False)
        self.assert_stop_approved(stop)
        self.assert_review_completed(project_root)
        self.assert_reviewer_done_logged(project_root, backend="codex")
