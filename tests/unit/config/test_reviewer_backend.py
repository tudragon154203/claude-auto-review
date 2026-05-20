import unittest

from claude_auto_review.config.settings import (
    DEFAULT_CLAUDE_REVIEWER_MODEL,
    DEFAULT_CODEX_REVIEWER_MODEL,
    DEFAULT_REVIEWER_BACKEND,
    DEFAULT_SETTINGS,
    REVIEWER_BACKENDS,
    SETTING_REVIEWER_BACKEND,
    SETTING_REVIEWER_MODEL,
    get_reviewer_backend,
    get_reviewer_model,
)


class TestReviewerBackendSetting(unittest.TestCase):
    def test_default_backend_is_claude(self):
        self.assertEqual(DEFAULT_REVIEWER_BACKEND, "claude")

    def test_default_settings_includes_backend(self):
        self.assertEqual(DEFAULT_SETTINGS[SETTING_REVIEWER_BACKEND], "claude")

    def test_default_settings_does_not_pin_single_reviewer_model(self):
        self.assertNotIn(SETTING_REVIEWER_MODEL, DEFAULT_SETTINGS)

    def test_reviewer_backends_contains_claude_and_codex(self):
        self.assertEqual(REVIEWER_BACKENDS, {"claude", "codex"})

    def test_get_reviewer_backend_returns_claude_when_unset(self):
        self.assertEqual(get_reviewer_backend({}), "claude")

    def test_get_reviewer_backend_returns_codex_when_set(self):
        self.assertEqual(get_reviewer_backend({SETTING_REVIEWER_BACKEND: "codex"}), "codex")

    def test_get_reviewer_backend_normalizes_case(self):
        self.assertEqual(get_reviewer_backend({SETTING_REVIEWER_BACKEND: "CODEX"}), "codex")

    def test_get_reviewer_backend_rejects_unknown(self):
        with self.assertRaises(ValueError):
            get_reviewer_backend({SETTING_REVIEWER_BACKEND: "unknown"})

    def test_get_reviewer_backend_rejects_typo(self):
        with self.assertRaises(ValueError):
            get_reviewer_backend({SETTING_REVIEWER_BACKEND: "codyx"})

    def test_get_reviewer_model_defaults_for_claude_backend(self):
        self.assertEqual(get_reviewer_model({}), DEFAULT_CLAUDE_REVIEWER_MODEL)

    def test_get_reviewer_model_defaults_for_codex_backend(self):
        self.assertEqual(
            get_reviewer_model({SETTING_REVIEWER_BACKEND: "codex"}),
            DEFAULT_CODEX_REVIEWER_MODEL,
        )

    def test_get_reviewer_model_prefers_explicit_override(self):
        self.assertEqual(
            get_reviewer_model(
                {
                    SETTING_REVIEWER_BACKEND: "codex",
                    SETTING_REVIEWER_MODEL: "custom-reviewer-model",
                }
            ),
            "custom-reviewer-model",
        )


if __name__ == "__main__":
    unittest.main()
