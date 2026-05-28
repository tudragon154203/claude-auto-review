import io
import json
import unittest
from urllib import error

from claude_auto_review.config.models import PluginSettings
from claude_auto_review.state.store.read import load_state
from claude_auto_review.stop.classifier.last_assistant_message import (
    classify_last_assistant_message,
)
from claude_auto_review.stop.classifier.models import CLASSIFICATION_EVENT
from claude_auto_review.stop.orchestration.context import RuntimeContext
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
        settings=settings if settings is not None else PluginSettings(),
        payload=payload if payload is not None else {"last_assistant_message": "some message"},
    )


class TestLastAssistantMessageErrors(StateTestCase, unittest.TestCase):
    def setUp(self):
        self.project_root = self.temp_project()
        self.client_id = "classifier-client"
        self.settings = PluginSettings(last_assistant_message_classifier_enabled=True)
        self.env = {
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:13456",
            "ANTHROPIC_API_KEY": "top-secret",
        }

    def test_classifier_disabled_returns_none(self):
        result = classify_last_assistant_message(
            _make_ctx(
                self.project_root,
                {"last_assistant_message": "Ship it."},
                PluginSettings(last_assistant_message_classifier_enabled=False),
            ),
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

        classify_last_assistant_message(
            _make_ctx(self.project_root, {"last_assistant_message": "Message"}, self.settings),
            env=self.env,
            urlopen=lambda req, timeout: _FakeResponse(payload),
        )

        state = load_state(self.project_root, self.client_id)
        self.assertEqual(state[-1].debugResponse, debug_response)

    def test_debug_response_not_logged_when_debug_off(self):
        payload = {"content": [{"text": "unknown"}], "id": "msg-nodebug"}

        classify_last_assistant_message(
            _make_ctx(
                self.project_root,
                {"last_assistant_message": "Message"},
                PluginSettings(
                    last_assistant_message_classifier_enabled=True,
                    debug=False,
                ),
            ),
            env=self.env,
            urlopen=lambda req, timeout: _FakeResponse(payload),
        )

        state = load_state(self.project_root, self.client_id)
        self.assertIsNone(state[-1].debugResponse)

    def test_timeout_returns_error_without_raising(self):
        result = classify_last_assistant_message(
            _make_ctx(self.project_root, {"last_assistant_message": "Message"}, self.settings),
            env=self.env,
            urlopen=lambda req, timeout: (_ for _ in ()).throw(TimeoutError()),
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
        result = classify_last_assistant_message(
            _make_ctx(self.project_root, {}, self.settings),
            env=self.env,
            urlopen=lambda req, timeout: _FakeResponse({"content": [{"text": "complete"}]}),
        )
        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.reason, "missing_message")
        state = load_state(self.project_root, self.client_id)
        self.assertEqual(state[-1].type, CLASSIFICATION_EVENT)

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
