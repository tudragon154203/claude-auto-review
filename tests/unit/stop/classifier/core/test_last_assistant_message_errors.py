import io
import json
import socket
import unittest
from unittest.mock import patch
from urllib import error

from claude_auto_review.state.store.read import load_state
from claude_auto_review.stop.classifier.core.models import CLASSIFICATION_EVENT
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


def _make_ctx(project_root, payload=None, settings=None):
    return RuntimeContext(
        project_root=project_root,
        client_id="classifier-client",
        settings=settings if settings is not None else {},
        payload=payload if payload is not None else {"last_assistant_message": "some message"},
    )


class TestLastAssistantMessageErrors(StateTestCase, unittest.TestCase):
    def setUp(self):
        self.project_root = self.temp_project()
        self.client_id = "classifier-client"
        self.settings = {
            "lastAssistantMessageClassifierEnabled": True,
        }
        self.env = {
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:13456",
            "ANTHROPIC_API_KEY": "top-secret",
        }

    def test_classifier_disabled_returns_none(self):
        result = classify_last_assistant_message(
            _make_ctx(self.project_root, {"last_assistant_message": "Ship it."}, {"lastAssistantMessageClassifierEnabled": False}),
            env=self.env,
            urlopen=lambda req, timeout: _FakeResponse({"content": [{"text": "complete"}]}),
        )
        self.assertIsNone(result)

    def test_missing_api_key_is_logged_as_error(self):
        result = classify_last_assistant_message(
            _make_ctx(self.project_root, {"last_assistant_message": "Ship it."}, self.settings),
            env={"ANTHROPIC_BASE_URL": "http://127.0.0.1:13456"},
            urlopen=lambda req, timeout: _FakeResponse({"content": [{"text": "complete"}]}),
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "missing_api_key")

    def test_debug_response_is_logged_for_all_labels(self):
        payload = {"content": [{"text": "unknown"}], "id": "msg-debug"}
        debug_response = json.dumps(payload, separators=(",", ":"))

        with patch("claude_auto_review.stop.classifier.core.last_assistant_message.log_event") as mock_log:
            classify_last_assistant_message(
                _make_ctx(self.project_root, {"last_assistant_message": "Message"}, self.settings),
                env=self.env,
                urlopen=lambda req, timeout: _FakeResponse(payload),
            )

        self.assertEqual(mock_log.call_args.kwargs["debugResponse"], debug_response)
        state = load_state(self.project_root, self.client_id)
        self.assertEqual(state[-1].debugResponse, debug_response)

    def test_debug_response_not_logged_when_debug_off(self):
        payload = {"content": [{"text": "unknown"}], "id": "msg-nodebug"}

        with patch("claude_auto_review.stop.classifier.core.last_assistant_message.log_event") as mock_log:
            classify_last_assistant_message(
                _make_ctx(self.project_root, {"last_assistant_message": "Message"}, {**self.settings, "debug": False}),
                env=self.env,
                urlopen=lambda req, timeout: _FakeResponse(payload),
            )

        self.assertNotIn("debugResponse", mock_log.call_args.kwargs)
        state = load_state(self.project_root, self.client_id)
        self.assertIsNone(state[-1].debugResponse)

    def test_timeout_returns_error_without_raising(self):
        result = classify_last_assistant_message(
            _make_ctx(self.project_root, {"last_assistant_message": "Message"}, self.settings),
            env=self.env,
            urlopen=lambda req, timeout: (_ for _ in ()).throw(socket.timeout()),
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "http_timeout")

    def test_http_error_returns_error_without_raising(self):
        def fake_urlopen(req, timeout):
            raise error.HTTPError(req.full_url, 503, "down", hdrs=None, fp=io.BytesIO(b""))

        result = classify_last_assistant_message(
            _make_ctx(self.project_root, {"last_assistant_message": "Message"}, self.settings),
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
            _make_ctx(self.project_root, {"last_assistant_message": "Message"}, self.settings),
            env=self.env,
            urlopen=lambda req, timeout: BadJsonResponse({}),
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "bad_response")

    def test_missing_message_is_logged_as_skipped(self):
        with patch("claude_auto_review.stop.classifier.core.last_assistant_message.log_event") as mock_log:
            result = classify_last_assistant_message(
                _make_ctx(self.project_root, {}, self.settings),
                env=self.env,
                urlopen=lambda req, timeout: _FakeResponse({"content": [{"text": "complete"}]}),
            )
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.reason, "missing_message")
        mock_log.assert_called_once()
        self.assertEqual(mock_log.call_args.args[1], CLASSIFICATION_EVENT)

    def test_missing_env_fails_open_and_persists_separate_state_type(self):
        result = classify_last_assistant_message(
            _make_ctx(self.project_root, {"last_assistant_message": "Message"}, self.settings),
            env={},
            urlopen=lambda req, timeout: _FakeResponse({"content": [{"text": "complete"}]}),
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "missing_base_url")
        state = load_state(self.project_root, self.client_id)
        self.assertEqual(state[-1].type, "last_assistant_message_classified")
        self.assertNotIn("top-secret", json.dumps([vars(r) for r in state]))


if __name__ == "__main__":
    unittest.main()
