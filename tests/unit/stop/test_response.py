import io
import json
import unittest
from unittest.mock import patch

from claude_auto_review.stop.response import (
    ResponseEmitter,
    StdoutResponseEmitter,
    approve_response,
    block_response,
)


class TestStdoutResponseEmitter(unittest.TestCase):
    @patch("builtins.print")
    def test_approve_empty_message_prints_json_no_stderr(self, mock_print):
        emitter = StdoutResponseEmitter()
        emitter.approve("")
        self.assertEqual(mock_print.call_count, 1)
        printed = mock_print.call_args[0][0]
        self.assertEqual(json.loads(printed), {"systemMessage": ""})

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("builtins.print")
    def test_approve_with_message_prints_json_and_stderr(self, mock_print, mock_stderr):
        emitter = StdoutResponseEmitter()
        emitter.approve("Hello")
        self.assertEqual(mock_print.call_count, 2)
        json_line = mock_print.call_args_list[0][0][0]
        self.assertEqual(json.loads(json_line), {"systemMessage": "Hello"})
        stderr_call = mock_print.call_args_list[1]
        self.assertEqual(stderr_call[1]["file"], mock_stderr)

    @patch("sys.stderr", new_callable=io.StringIO)
    @patch("builtins.print")
    def test_block_prints_json_and_stderr(self, mock_print, mock_stderr):
        emitter = StdoutResponseEmitter()
        emitter.block("msg", "feedback text")
        self.assertEqual(mock_print.call_count, 2)
        json_line = mock_print.call_args_list[0][0][0]
        parsed = json.loads(json_line)
        self.assertEqual(parsed["decision"], "block")
        self.assertEqual(parsed["reason"], "feedback text")
        self.assertEqual(parsed["systemMessage"], "msg")


class TestResponseEmitterProtocol(unittest.TestCase):
    def test_protocol_is_runtime_checkable(self):
        emitter = StdoutResponseEmitter()
        self.assertIsInstance(emitter, ResponseEmitter)

    def test_non_compliant_not_instance(self):
        self.assertNotIsInstance(42, ResponseEmitter)


class TestModuleFunctions(unittest.TestCase):
    @patch("claude_auto_review.stop.response._default_emitter")
    def test_approve_response_delegates(self, mock_emitter):
        approve_response("test")
        mock_emitter.approve.assert_called_once_with("test")

    @patch("claude_auto_review.stop.response._default_emitter")
    def test_block_response_delegates(self, mock_emitter):
        block_response("msg", "fb")
        mock_emitter.block.assert_called_once_with("msg", "fb")


if __name__ == "__main__":
    unittest.main()
