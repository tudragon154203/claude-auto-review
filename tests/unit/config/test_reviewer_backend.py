import unittest

from claude_auto_review.config.settings.models import (
    DEFAULT_CLAUDE_REVIEWER_MODEL,
    DEFAULT_CODEX_REVIEWER_MODEL,
    DEFAULT_REVIEWER_BACKEND,
    REVIEWER_BACKENDS,
    PluginSettings,
)
from claude_auto_review.config.reviewer.backends import (
    DEFAULT_REVIEWER_MODELS,
    resolve_reviewer_backend,
    resolve_reviewer_model,
)


class TestReviewerBackendSetting(unittest.TestCase):
    def test_default_backend_is_claude(self):
        self.assertEqual(DEFAULT_REVIEWER_BACKEND, "claude")

    def test_default_settings_includes_backend(self):
        self.assertEqual(PluginSettings().to_mapping()["reviewerBackend"], "claude")

    def test_default_settings_includes_resolved_reviewer_model(self):
        self.assertEqual(PluginSettings().to_mapping()["reviewerModel"], DEFAULT_CLAUDE_REVIEWER_MODEL)

    def test_to_mapping_orders_related_keys_together(self):
        self.assertEqual(
            list(PluginSettings().to_mapping().keys()),
            [
                "enabled",
                "rulesFile",
                "includeExtensions",
                "skipExtensions",
                "reviewerBackend",
                "reviewerModel",
                "reviewerTimeoutSeconds",
                "reviewFeedbackMaxChars",
                "maxStopPasses",
                "minimumBlockingSeverity",
                "pendingReviewTimeoutHours",
                "lastAssistantMessageClassifierEnabled",
                "classifierModel",
                "lastAssistantMessageClassifierTimeoutSeconds",
                "staleClientTimeoutHours",
                "debug",
            ],
        )

    def test_reviewer_backends_contains_all_three(self):
        self.assertEqual(REVIEWER_BACKENDS, frozenset({"claude", "codex", "opencode"}))

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

    def test_get_reviewer_backend_returns_opencode_when_set(self):
        self.assertEqual(
            PluginSettings.from_mapping({"reviewerBackend": "opencode"}).resolved_reviewer_backend(),
            "opencode",
        )

    def test_get_reviewer_backend_normalizes_opencode_case(self):
        self.assertEqual(
            PluginSettings.from_mapping({"reviewerBackend": "OpenCode"}).resolved_reviewer_backend(),
            "opencode",
        )

    def test_get_reviewer_model_defaults_for_opencode_backend(self):
        self.assertEqual(
            PluginSettings.from_mapping({"reviewerBackend": "opencode"}).resolved_reviewer_model(),
            "default",
        )


class TestResolveFunctions(unittest.TestCase):
    def test_resolve_reviewer_backend_returns_known(self):
        for backend in ("claude", "codex", "opencode"):
            self.assertEqual(resolve_reviewer_backend(backend), backend)

    def test_resolve_reviewer_backend_rejects_unknown(self):
        with self.assertRaises(ValueError):
            resolve_reviewer_backend("unknown")

    def test_resolve_reviewer_model_returns_explicit(self):
        self.assertEqual(resolve_reviewer_model("custom-model", backend="claude"), "custom-model")

    def test_resolve_reviewer_model_defaults_per_backend(self):
        for backend, expected in DEFAULT_REVIEWER_MODELS.items():
            self.assertEqual(resolve_reviewer_model(None, backend=backend), expected)

    def test_resolve_reviewer_model_fallback_for_unknown_backend(self):
        self.assertEqual(resolve_reviewer_model(None, backend="nonexistent"), DEFAULT_REVIEWER_MODELS["claude"])


if __name__ == "__main__":
    unittest.main()
