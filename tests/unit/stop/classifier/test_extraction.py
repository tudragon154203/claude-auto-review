import unittest

from claude_auto_review.stop.classifier.extraction import extract_last_assistant_message_text


class TestExtraction(unittest.TestCase):
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
