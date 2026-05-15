import io
import json
import socket
import unittest
from urllib import error

from claude_auto_review.stop.classifier.core.client import _parse_classifier_label, call_classifier_api, sanitize_base_url


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestClassifierClient(unittest.TestCase):
    def test_sanitize_base_url_rejects_non_strings_and_invalid_urls(self):
        self.assertEqual(sanitize_base_url(None), "")
        self.assertEqual(sanitize_base_url(""), "")
        self.assertEqual(sanitize_base_url("http://token@example.test:13456/proxy/?secret=1#frag"), "http://example.test:13456/proxy")
        self.assertEqual(sanitize_base_url("http://["), "")

    def test_parse_classifier_label_ignores_non_text_blocks(self):
        label, reason = _parse_classifier_label(
            {
                "content": [
                    {"type": "thinking", "thinking": "maybe"},
                    {"type": "text", "text": "complete"},
                ]
            }
        )
        self.assertEqual(label, "complete")
        self.assertEqual(reason, "parsed_label")

    def test_parse_classifier_label_rejects_non_objects(self):
        label, reason = _parse_classifier_label(["not", "a", "dict"])
        self.assertEqual(label, "unknown")
        self.assertEqual(reason, "bad_response")

    def test_call_classifier_api_maps_http_and_timeout_errors(self):
        started_at = 0.0

        def http_error(_req, timeout):
            raise error.HTTPError("https://example.test", 503, "down", hdrs=None, fp=io.BytesIO(b""))

        result = call_classifier_api("message", "http://example.test", "key", started_at, 5, urlopen=http_error)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "http_error")
        self.assertEqual(result.http_status, 503)

        def timeout_error(_req, timeout):
            raise error.URLError(socket.timeout())

        result = call_classifier_api("message", "http://example.test", "key", started_at, 5, urlopen=timeout_error)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "http_timeout")

    def test_call_classifier_api_handles_bad_json_malformed_shape_and_unexpected_exceptions(self):
        started_at = 0.0

        def bad_json(_req, timeout):
            return _FakeResponse(b"{not-json")

        result = call_classifier_api("message", "http://example.test", "key", started_at, 5, urlopen=bad_json)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "bad_response")

        def malformed_shape(_req, timeout):
            return _FakeResponse(["not", "an", "object"])

        result = call_classifier_api("message", "http://example.test", "key", started_at, 5, urlopen=malformed_shape)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "bad_response")

        def boom(_req, timeout):
            raise RuntimeError("boom")

        result = call_classifier_api("message", "http://example.test", "key", started_at, 5, urlopen=boom)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "http_error")


if __name__ == "__main__":
    unittest.main()
