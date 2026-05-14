import json
import unittest

from claude_auto_review.stop.classifier.models import (
    CLASSIFIER_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
)
from claude_auto_review.stop.classifier.last_assistant_message import (
    classify_last_assistant_message,
)

from tests.unit.state.support import StateTestCase


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestLastAssistantMessageClassifier(StateTestCase, unittest.TestCase):
    def setUp(self):
        self.project_root = self.temp_project()
        self.client_id = "classifier-client"
        self.settings = {
            "lastAssistantMessageClassifierEnabled": True,
            "lastAssistantMessageClassifierTimeoutSeconds": DEFAULT_TIMEOUT_SECONDS,
        }
        self.env = {
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:13456",
            "ANTHROPIC_API_KEY": "top-secret",
        }

    def test_sends_expected_request_shape(self):
        seen = {}

        def fake_urlopen(req, timeout):
            seen["url"] = req.full_url
            seen["timeout"] = timeout
            seen["headers"] = dict(req.header_items())
            seen["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse({"content": [{"type": "text", "text": "complete"}]})

        result = classify_last_assistant_message(
            self.project_root,
            self.client_id,
            {"last_assistant_message": "Ship it."},
            self.settings,
            env=self.env,
            urlopen=fake_urlopen,
        )

        self.assertEqual(result.status, "complete")
        self.assertEqual(seen["url"], "http://127.0.0.1:13456/v1/messages")
        self.assertEqual(seen["timeout"], DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(seen["headers"]["Anthropic-version"], "2023-06-01")
        self.assertEqual(seen["headers"]["X-api-key"], "top-secret")
        self.assertEqual(seen["body"]["model"], CLASSIFIER_MODEL)
        self.assertEqual(seen["body"]["max_tokens"], 8)
        self.assertEqual(seen["body"]["temperature"], 0)
        self.assertEqual(seen["body"]["stop_sequences"], ["\n"])
        self.assertIn("exactly one lowercase label", seen["body"]["system"])
        self.assertIn("Ship it.", seen["body"]["messages"][0]["content"][0]["text"])
        self.assertTrue(seen["body"]["messages"][0]["content"][0]["text"].endswith("\n\nLabel:"))

    def test_invalid_timeout_falls_back_to_default(self):
        seen = {}

        def fake_urlopen(req, timeout):
            seen["timeout"] = timeout
            return _FakeResponse({"content": [{"text": "complete"}]})

        result = classify_last_assistant_message(
            self.project_root,
            self.client_id,
            {"last_assistant_message": "Ship it."},
            {"lastAssistantMessageClassifierEnabled": True, "lastAssistantMessageClassifierTimeoutSeconds": "nope"},
            env=self.env,
            urlopen=fake_urlopen,
        )
        self.assertEqual(result.status, "complete")
        self.assertEqual(seen["timeout"], DEFAULT_TIMEOUT_SECONDS)

    def test_accepts_exact_labels(self):
        for label in ("complete", "incomplete", "unknown"):
            with self.subTest(label=label):
                result = classify_last_assistant_message(
                    self.project_root,
                    self.client_id,
                    {"last_assistant_message": "Message"},
                    self.settings,
                    env=self.env,
                    urlopen=lambda req, timeout, value=label: _FakeResponse({"content": [{"text": value}]}),
                )
                self.assertEqual(result.status, label)
                self.assertEqual(result.reason, "parsed_label")

    def test_unexpected_output_downgrades_to_unknown(self):
        payload = {"content": [{"text": "maybe"}]}
        result = classify_last_assistant_message(
            self.project_root,
            self.client_id,
            {"last_assistant_message": "Message"},
            self.settings,
            env=self.env,
            urlopen=lambda req, timeout: _FakeResponse(payload),
        )
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "invalid_label")
        self.assertEqual(result.debug_response, json.dumps(payload, separators=(",", ":")))

    def test_ignores_thinking_blocks_when_parsing_label(self):
        payload = {
            "content": [
                {"type": "thinking", "thinking": "The answer is probably incomplete."},
                {"type": "text", "text": "complete"},
            ]
        }
        result = classify_last_assistant_message(
            self.project_root,
            self.client_id,
            {"last_assistant_message": "Message"},
            self.settings,
            env=self.env,
            urlopen=lambda req, timeout: _FakeResponse(payload),
        )
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.reason, "parsed_label")

    def test_accepts_label_with_extra_text(self):
        payload = {"content": [{"type": "text", "text": "complete\nfinal answer"}]}
        result = classify_last_assistant_message(
            self.project_root,
            self.client_id,
            {"last_assistant_message": "Message"},
            self.settings,
            env=self.env,
            urlopen=lambda req, timeout: _FakeResponse(payload),
        )
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.reason, "parsed_label")


if __name__ == "__main__":
    unittest.main()
