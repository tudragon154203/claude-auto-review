import json
import unittest

from claude_auto_review.config.settings import DEFAULT_CLASSIFIER_MODEL
from claude_auto_review.stop.classifier.core.models import (
    DEFAULT_TIMEOUT_SECONDS,
)
from claude_auto_review.stop.classifier.core.last_assistant_message import (
    classify_last_assistant_message,
)
from claude_auto_review.stop.orchestration.core.context import RuntimeContext

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

    def _ctx(self, payload=None, settings=None):
        return RuntimeContext(
            project_root=self.project_root,
            client_id=self.client_id,
            settings=settings if settings is not None else self.settings,
            payload=payload if payload is not None else {"last_assistant_message": "Ship it."},
        )

    def test_sends_expected_request_shape(self):
        seen = {}

        def fake_urlopen(req, timeout):
            seen["url"] = req.full_url
            seen["timeout"] = timeout
            seen["headers"] = dict(req.header_items())
            seen["body"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse({"content": [{"type": "text", "text": "complete"}]})

        result = classify_last_assistant_message(
            self._ctx(),
            env=self.env,
            urlopen=fake_urlopen,
        )

        self.assertEqual(result.status, "complete")
        self.assertEqual(seen["url"], "http://127.0.0.1:13456/v1/messages")
        self.assertEqual(seen["timeout"], DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(seen["headers"]["Anthropic-version"], "2023-06-01")
        self.assertEqual(seen["headers"]["X-api-key"], "top-secret")
        self.assertEqual(seen["body"]["model"], DEFAULT_CLASSIFIER_MODEL)
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
            self._ctx(
                settings={"lastAssistantMessageClassifierEnabled": True, "lastAssistantMessageClassifierTimeoutSeconds": "nope"},
            ),
            env=self.env,
            urlopen=fake_urlopen,
        )
        self.assertEqual(result.status, "complete")
        self.assertEqual(seen["timeout"], DEFAULT_TIMEOUT_SECONDS)

    def test_accepts_exact_labels(self):
        for label in ("complete", "incomplete", "unknown"):
            with self.subTest(label=label):
                response_payload = {"content": [{"text": label}]}
                result = classify_last_assistant_message(
                    self._ctx(payload={"last_assistant_message": "Message"}),
                    env=self.env,
                    urlopen=lambda req, timeout, value=label: _FakeResponse(response_payload),
                )
                self.assertEqual(result.status, label)
                self.assertEqual(result.reason, "parsed_label")
                self.assertEqual(result.debug_response, json.dumps(response_payload, separators=(",", ":")))

    def test_unexpected_output_downgrades_to_unknown(self):
        payload = {"content": [{"text": "maybe"}]}
        result = classify_last_assistant_message(
            self._ctx(payload={"last_assistant_message": "Message"}),
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
            self._ctx(payload={"last_assistant_message": "Message"}),
            env=self.env,
            urlopen=lambda req, timeout: _FakeResponse(payload),
        )
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.reason, "parsed_label")
        self.assertEqual(result.debug_response, json.dumps(payload, separators=(",", ":")))

    def test_accepts_label_with_extra_text(self):
        payload = {"content": [{"type": "text", "text": "complete\nfinal answer"}]}
        result = classify_last_assistant_message(
            self._ctx(payload={"last_assistant_message": "Message"}),
            env=self.env,
            urlopen=lambda req, timeout: _FakeResponse(payload),
        )
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.reason, "parsed_label")


if __name__ == "__main__":
    unittest.main()