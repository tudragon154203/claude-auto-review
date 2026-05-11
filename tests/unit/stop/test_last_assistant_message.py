import io
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import error

from claude_auto_review.state.store_read import load_state
from claude_auto_review.stop.last_assistant_message import (
    CLASSIFICATION_EVENT,
    CLASSIFIER_MODEL,
    classify_last_assistant_message,
    extract_last_assistant_message_text,
    sanitize_base_url,
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


class TestLastAssistantMessageExtraction(unittest.TestCase):
    def test_extracts_last_assistant_message_string(self):
        payload = {"last_assistant_message": "Final answer."}
        self.assertEqual(extract_last_assistant_message_text(payload), "Final answer.")

    def test_extracts_camel_case_message(self):
        payload = {"lastAssistantMessage": {"content": "Wrapped answer"}}
        self.assertEqual(extract_last_assistant_message_text(payload), "Wrapped answer")

    def test_extracts_nested_conversation_blocks(self):
        payload = {
            "conversation": {
                "last_assistant_message": {
                    "content": [
                        {"type": "text", "text": "First"},
                        {"type": "tool_use", "name": "noop"},
                        {"type": "text", "text": " second"},
                    ]
                }
            }
        }
        self.assertEqual(extract_last_assistant_message_text(payload), "First second")

    def test_returns_empty_for_missing_message(self):
        self.assertEqual(extract_last_assistant_message_text({}), "")

    def test_sanitize_base_url_removes_query_and_user_info(self):
        base_url = "http://token@example.test:13456/proxy/?secret=1#frag"
        self.assertEqual(sanitize_base_url(base_url), "http://example.test:13456/proxy")


class TestLastAssistantMessageClassifier(StateTestCase, unittest.TestCase):
    def setUp(self):
        self.project_root = self.temp_project()
        self.client_id = "classifier-client"
        self.settings = {
            "lastAssistantMessageClassifierEnabled": True,
            "lastAssistantMessageClassifierTimeoutSeconds": 10,
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
        self.assertEqual(seen["timeout"], 10.0)
        self.assertEqual(seen["headers"]["Anthropic-version"], "2023-06-01")
        self.assertEqual(seen["headers"]["X-api-key"], "top-secret")
        self.assertEqual(seen["body"]["model"], CLASSIFIER_MODEL)
        self.assertEqual(seen["body"]["max_tokens"], 16)
        self.assertEqual(seen["body"]["temperature"], 0)
        self.assertIn("Ship it.", seen["body"]["messages"][0]["content"][0]["text"])

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
        result = classify_last_assistant_message(
            self.project_root,
            self.client_id,
            {"last_assistant_message": "Message"},
            self.settings,
            env=self.env,
            urlopen=lambda req, timeout: _FakeResponse({"content": [{"text": "maybe"}]}),
        )
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "invalid_label")

    def test_timeout_returns_error_without_raising(self):
        result = classify_last_assistant_message(
            self.project_root,
            self.client_id,
            {"last_assistant_message": "Message"},
            self.settings,
            env=self.env,
            urlopen=lambda req, timeout: (_ for _ in ()).throw(socket.timeout()),
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "http_timeout")

    def test_http_error_returns_error_without_raising(self):
        def fake_urlopen(req, timeout):
            raise error.HTTPError(req.full_url, 503, "down", hdrs=None, fp=io.BytesIO(b""))

        result = classify_last_assistant_message(
            self.project_root,
            self.client_id,
            {"last_assistant_message": "Message"},
            self.settings,
            env=self.env,
            urlopen=fake_urlopen,
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "http_error")
        self.assertEqual(result.http_status, 503)

    def test_malformed_json_returns_error_without_raising(self):
        class BadJsonResponse(_FakeResponse):
            def read(self):
                return b"{not-json"

        result = classify_last_assistant_message(
            self.project_root,
            self.client_id,
            {"last_assistant_message": "Message"},
            self.settings,
            env=self.env,
            urlopen=lambda req, timeout: BadJsonResponse({}),
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "bad_response")

    def test_missing_message_is_logged_as_skipped(self):
        with patch("claude_auto_review.stop.last_assistant_message.log_event") as mock_log:
            result = classify_last_assistant_message(
                self.project_root,
                self.client_id,
                {},
                self.settings,
                env=self.env,
                urlopen=lambda req, timeout: _FakeResponse({"content": [{"text": "complete"}]}),
            )
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.reason, "missing_message")
        mock_log.assert_called_once()
        self.assertEqual(mock_log.call_args.args[1], CLASSIFICATION_EVENT)

    def test_missing_env_fails_open_and_persists_separate_state_type(self):
        result = classify_last_assistant_message(
            self.project_root,
            self.client_id,
            {"last_assistant_message": "Message"},
            self.settings,
            env={},
            urlopen=lambda req, timeout: _FakeResponse({"content": [{"text": "complete"}]}),
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "missing_base_url")
        state = load_state(self.project_root, self.client_id)
        self.assertEqual(state[-1]["type"], "assistant_message_classification")
        self.assertNotIn("top-secret", json.dumps(state))
