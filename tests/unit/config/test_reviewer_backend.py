import unittest

from claude_auto_review.config.models import (
    DEFAULT_CLAUDE_REVIEWER_MODEL,
    DEFAULT_CODEX_REVIEWER_MODEL,
    DEFAULT_REVIEWER_BACKEND,
    PluginSettings,
    REVIEWER_BACKENDS,
)


class TestReviewerBackendSetting(unittest.TestCase):
    def test_default_backend_is_claude(self):
        self.assertEqual(DEFAULT_REVIEWER_BACKEND, "claude")

    def test_default_settings_includes_backend(self):
        self.assertEqual(PluginSettings().to_mapping()["reviewerBackend"], "claude")

    def test_default_settings_does_not_pin_single_reviewer_model(self):
        self.assertNotIn("reviewerModel", PluginSettings().to_mapping())

    def test_reviewer_backends_contains_claude_and_codex(self):
        self.assertEqual(REVIEWER_BACKENDS, frozenset({"claude", "codex"}))

    def test_get_reviewer_backend_returns_claude_when_unset(self):
        self.assertEqual(PluginSettings().resolved_reviewer_backend(), "claude")

    def test_get_reviewer_backend_returns_codex_when_set(self):
        self.assertEqual(
            PluginSettings.from_mapping({"reviewerBackend": "codex"}).resolved_reviewer_backend(),
            "codex",
        )

    def test_get_reviewer_backend_normalizes_case(self):
        self.assertEqual(
            PluginSettings.from_mapping({"reviewerBackend": "CODEX"}).resolved_reviewer_backend(),
            "codex",
        )

    def test_get_reviewer_backend_rejects_unknown(self):
        with self.assertRaises(ValueError):
            PluginSettings.from_mapping({"reviewerBackend": "unknown"}).resolved_reviewer_backend()

    def test_get_reviewer_backend_rejects_typo(self):
        with self.assertRaises(ValueError):
            PluginSettings.from_mapping({"reviewerBackend": "codyx"}).resolved_reviewer_backend()

    def test_get_reviewer_model_defaults_for_claude_backend(self):
        self.assertEqual(PluginSettings().resolved_reviewer_model(), DEFAULT_CLAUDE_REVIEWER_MODEL)

    def test_get_reviewer_model_defaults_for_codex_backend(self):
        self.assertEqual(
            PluginSettings.from_mapping({"reviewerBackend": "codex"}).resolved_reviewer_model(),
            DEFAULT_CODEX_REVIEWER_MODEL,
        )

    def test_get_reviewer_model_prefers_explicit_override(self):
        self.assertEqual(
            PluginSettings.from_mapping(
                {"reviewerBackend": "codex", "reviewerModel": "custom-reviewer-model"}
            ).resolved_reviewer_model(),
            "custom-reviewer-model",
        )


if __name__ == "__main__":
    unittest.main()
