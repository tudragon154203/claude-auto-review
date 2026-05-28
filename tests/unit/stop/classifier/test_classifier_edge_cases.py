import unittest

from claude_auto_review.stop.classifier.client import sanitize_base_url
from claude_auto_review.stop.classifier.extraction import extract_last_assistant_message_text
from claude_auto_review.stop.classifier.response import parse_classifier_label


class TestClassifierEdgeCases(unittest.TestCase):
    def test_extract_last_assistant_message_text_non_dict_payload(self):
        self.assertEqual(extract_last_assistant_message_text("not-a-dict"), "")
        self.assertEqual(extract_last_assistant_message_text(None), "")

    def test_extract_last_assistant_message_text_unrecognized_structure(self):
        payload = {"weird": "structure"}
        self.assertEqual(extract_last_assistant_message_text(payload), "")

    def test_extract_last_assistant_message_text_missing_content_in_camel_case(self):
        payload = {"lastAssistantMessage": {}}
        self.assertEqual(extract_last_assistant_message_text(payload), "")

    def test_parse_classifier_label_non_dict_fallback(self):
        label, reason = parse_classifier_label("not-a-dict")
        self.assertEqual(label, "unknown")
        self.assertEqual(reason, "bad_response")

    def test_sanitize_base_url_trailing_slash(self):
        self.assertEqual(sanitize_base_url("https://api.example.com/"), "https://api.example.com")


if __name__ == "__main__":
    unittest.main()
