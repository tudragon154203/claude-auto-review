import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_auto_review.stop.orchestration.context import RuntimeContext
from claude_auto_review.stop.reviews.codex_output import _extract_codex_final_message
from claude_auto_review.stop.reviews.prompt_runner import (
    _run_claude_cli,
    attempt_stop_autocomplete,
)
from claude_auto_review.stop.reviews.review_args import (
    _build_claude_review_args,
    _build_codex_review_args,
)


class TestPromptRunnerCodex(unittest.TestCase):
    def _ctx(self):
        return RuntimeContext(project_root=Path('/fake'), client_id='client-1')

    def test_build_codex_review_args(self):
        self.assertEqual(
            _build_codex_review_args('gpt-5'),
            ['exec', '--json', '--skip-git-repo-check', '--sandbox', 'read-only', '--model', 'gpt-5', '-'],
        )

    def test_build_claude_review_args(self):
        self.assertEqual(
            _build_claude_review_args('claude-sonnet-4-6')[:4],
            ['--print', '--bare', '--allowedTools', 'Read'],
        )

    def test_extract_codex_final_message_uses_turn_completed_message(self):
        stdout = '{"type":"turn.completed","message":"Clean - no issues found."}\n'
        self.assertEqual(_extract_codex_final_message(stdout), 'Clean - no issues found.')

    def test_extract_codex_final_message_handles_structured_msg(self):
        stdout = '{"type":"turn.completed","message":{"text":"Clean from dict."}}\n'
        self.assertEqual(_extract_codex_final_message(stdout), 'Clean from dict.')

        stdout_list = '{"type":"turn.completed","message":[{"text":"Clean from list dict."}]}\n'
        self.assertEqual(_extract_codex_final_message(stdout_list), 'Clean from list dict.')

    def test_extract_codex_final_message_handles_agent_message_item(self):
        stdout = (
            '{"type":"thread.started","thread_id":"t1"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"# Review\\n\\n## Verdict\\n\\nClean - no issues found. Claude may stop."}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\n'
        )
        self.assertEqual(
            _extract_codex_final_message(stdout),
            '# Review\n\n## Verdict\n\nClean - no issues found. Claude may stop.',
        )

    def test_extract_codex_final_message_uses_last_completed_message(self):
        stdout = (
            '{"type":"turn.completed","message":"First"}\n'
            '{"type":"turn.completed","message":"Second"}\n'
        )
        self.assertEqual(_extract_codex_final_message(stdout), 'Second')

    def test_attempt_stop_autocomplete_rejects_unknown_backend(self):
        review_path = Path(tempfile.gettempdir()) / 'review-unknown.md'
        prompt_file = Path(tempfile.gettempdir()) / 'prompt-unknown.md'
        prompt_file.write_text('system prompt', encoding='utf-8')

        with self.assertRaises(ValueError):
            attempt_stop_autocomplete(
                self._ctx(),
                'rev-3',
                review_path,
                prompt_file,
                'user prompt',
                reviewer_timeout_seconds=5,
                model='claude-sonnet-4-6',
                backend='codexx',
            )

    @patch('claude_auto_review.stop.reviews.review_result.normalize_review_verdict_content', side_effect=lambda s, client_id=None, minimum_blocking_severity="medium": s)
    @patch('claude_auto_review.stop.reviews.prompt_runner.run_captured')
    @patch('claude_auto_review.stop.reviews.prompt_runner.shutil.which', return_value='/usr/bin/codex')
    def test_attempt_stop_autocomplete_uses_codex_backend(self, mock_which, mock_run, _mock_norm):
        review_path = Path(tempfile.gettempdir()) / 'review.md'
        prompt_file = Path(tempfile.gettempdir()) / 'prompt.md'
        prompt_file.write_text('system prompt', encoding='utf-8')
        mock_run.return_value = MagicMock(
            stdout='{"type":"turn.completed","message":{"text":"Clean - no issues found."}}\n',
            stderr='',
            returncode=0,
            args=['/usr/bin/codex'],
        )

        result = attempt_stop_autocomplete(
            self._ctx(),
            'rev-1',
            review_path,
            prompt_file,
            'user prompt',
            reviewer_timeout_seconds=5,
            model='gpt-5',
            backend='codex',
        )

        self.assertEqual(result.status, 'output_written')
        mock_which.assert_called_once_with('codex')
        self.assertIn('--json', mock_run.call_args.args[0])
        self.assertIn('--skip-git-repo-check', mock_run.call_args.args[0])
        self.assertEqual(mock_run.call_args.kwargs['input'], 'system prompt\n\nuser prompt')

    @patch('claude_auto_review.stop.reviews.review_result.normalize_review_verdict_content', side_effect=lambda s, client_id=None, minimum_blocking_severity="medium": s)
    @patch('claude_auto_review.stop.reviews.prompt_runner.run_captured')
    @patch('claude_auto_review.stop.reviews.prompt_runner.shutil.which', return_value='/usr/bin/claude')
    def test_attempt_stop_autocomplete_uses_claude_backend(self, mock_which, mock_run, _mock_norm):
        review_path = Path(tempfile.gettempdir()) / 'review-claude.md'
        prompt_file = Path(tempfile.gettempdir()) / 'prompt-claude.md'
        prompt_file.write_text('system prompt', encoding='utf-8')
        mock_run.return_value = MagicMock(stdout='Clean - no issues found.', stderr='', returncode=0)

        result = attempt_stop_autocomplete(
            self._ctx(),
            'rev-2',
            review_path,
            prompt_file,
            'user prompt',
            reviewer_timeout_seconds=5,
            model='claude-sonnet-4-6',
            backend='claude',
        )

        self.assertEqual(result.status, 'output_written')
        mock_which.assert_called_once_with('claude')
        self.assertEqual(mock_run.call_args.kwargs.get('input'), None)
        self.assertIn('user prompt', mock_run.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
