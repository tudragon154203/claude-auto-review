import unittest

from tests.e2e.stop_hook_autocomplete.support import StopHookAutocompleteTestCase
from tests.support import real_claude_cli_available, real_codex_cli_available, real_opencode_cli_available


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

    @unittest.skipUnless(real_opencode_cli_available(), "real opencode CLI not available")
    def test_stop_hook_auto_completes_review_with_real_opencode(self):
        project_root = self.temp_project()
        self.configure_opencode_backend(project_root)
        self.create_tracked_app(project_root)

        self.stop(project_root, use_fake_claude=False, use_fake_opencode=False)
        # The real model may return a clean or findings verdict.
        # Either way the review pipeline must have run and produced output.
        self.assert_reviewer_done_logged(project_root, backend="opencode")
        review_path = self.latest_review_path(project_root)
        self.assertTrue(review_path.exists(), "Review file should be written")
        content = review_path.read_text(encoding="utf-8")
        self.assertTrue(len(content) > 0, "Review file should have content")
