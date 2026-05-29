import unittest

from claude_auto_review.stop.reviews.codex_output import _extract_codex_final_message


class TestExtractCodexFinalMessage(unittest.TestCase):
    def test_uses_turn_completed_message(self):
        stdout = '{"type":"turn.completed","message":"Clean - no issues found."}\n'
        self.assertEqual(_extract_codex_final_message(stdout), "Clean - no issues found.")

    def test_handles_structured_msg(self):
        stdout = '{"type":"turn.completed","message":{"text":"Clean from dict."}}\n'
        self.assertEqual(_extract_codex_final_message(stdout), "Clean from dict.")

        stdout_list = '{"type":"turn.completed","message":[{"text":"Clean from list dict."}]}\n'
        self.assertEqual(_extract_codex_final_message(stdout_list), "Clean from list dict.")

    def test_handles_interleaved_raw_text(self):
        stdout = (
            "Looking at the diff and current file snapshots, I'll analyze the changes...\n"
            '{"type":"thread.started","thread_id":"t1"}\n'
            '{"type":"turn.started"}\n'
            '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"\\n"}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":56}}\n'
        )
        result = _extract_codex_final_message(stdout)
        self.assertIn("Looking at the diff", result)
        self.assertNotIn("turn.started", result)

    def test_keeps_brace_prefixed_lines(self):
        stdout = "First line of output\n{not valid json but should be kept}\nSecond line of output\n"
        self.assertEqual(
            _extract_codex_final_message(stdout),
            "First line of output\n{not valid json but should be kept}\nSecond line of output",
        )

    def test_preserves_non_dict_json_as_raw(self):
        stdout = "First line\n" '["a", "b"]\n' '"just a string"\n' "Second line\n"
        self.assertEqual(_extract_codex_final_message(stdout), 'First line\n["a", "b"]\n"just a string"\nSecond line')

    def test_strips_preamble_if_header_found(self):
        stdout = "Certainly! I will review the changes now.\n" "# Review rev-123 - 2026-05-25\n" "## Findings\n" "None."
        result = _extract_codex_final_message(stdout)
        self.assertTrue(result.startswith("# Review rev-123 - 2026-05-25"))

    def test_uses_last_review_header(self):
        stdout = (
            "The format should be: # Review rev-OLD - old date\n"
            "No wait, the format is different. Let me check: # Review rev-123 - 2026-05-25\n"
            "## Findings\n"
            "None."
        )
        self.assertEqual(_extract_codex_final_message(stdout), "# Review rev-123 - 2026-05-25\n## Findings\nNone.")

    def test_accumulates_all_parts(self):
        stdout = (
            '{"type":"item.completed","item":{"type":"agent_message","text":"Part 1"}}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"Part 2"}}\n'
        )
        self.assertEqual(_extract_codex_final_message(stdout), "Part 1\nPart 2")

    def test_skips_empty_parts(self):
        stdout = (
            '{"type":"item.completed","item":{"type":"agent_message","text":"Real content"}}\n'
            '{"type":"item.completed","item":{"id":"i1","type":"agent_message","text":"   "}}\n'
        )
        self.assertEqual(_extract_codex_final_message(stdout), "Real content")

    def test_falls_back_to_raw_if_no_meaningful_json(self):
        stdout = '{"type":"turn.started"}\n{"type":"turn.completed"}\n'
        self.assertEqual(_extract_codex_final_message(stdout), stdout)


if __name__ == "__main__":
    unittest.main()
