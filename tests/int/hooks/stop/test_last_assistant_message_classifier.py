import json
import unittest

from claude_auto_review.config.constants.defaults import DEFAULT_CLASSIFIER_MODEL
from tests.int.hooks.support import HookTestCase
from tests.support_classifier_server import start_classifier_server
from tests.support_paths import client_dir


class TestLastAssistantMessageClassifierHook(HookTestCase, unittest.TestCase):
    def _read_log_entries(self, project_root):
        log_path = client_dir(project_root) / "state.jsonl"
        return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_stop_hook_logs_complete_classification_without_changing_clean_stop(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        server, base_url = start_classifier_server(label="complete")
        try:
            payload = json.dumps({"last_assistant_message": "All done. Final answer above."})
            result = self.run_python(
                "hooks/stop_hook.py",
                project_root,
                input_text=payload,
                env_overrides={
                    "ANTHROPIC_BASE_URL": base_url,
                    "ANTHROPIC_API_KEY": "secret-key",
                    "PATH": "",
                },
                use_fake_claude=False,
            )
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(server.requests), 1)
        self.assertEqual(server.requests[0]["body"]["model"], DEFAULT_CLASSIFIER_MODEL)
        entries = [
            e for e in self._read_log_entries(project_root) if e.get("type") == "last_assistant_message_classified"
        ]
        self.assertEqual(entries[-1]["status"], "complete")
        self.assertEqual(entries[-1]["reason"], "parsed_label")
        self.assertEqual(entries[-1]["baseUrl"], base_url)
        self.assertNotIn("secret-key", json.dumps(entries[-1]))
        review_events = [e for e in self._read_log_entries(project_root) if e.get("type") == "review_prompt_created"]
        self.assertEqual(len(review_events), 1)

    def test_stop_hook_allows_continue_on_incomplete_classification(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        server, base_url = start_classifier_server(label="incomplete")
        try:
            payload = json.dumps({"last_assistant_message": {"content": "Still working."}})
            result = self.run_python(
                "hooks/stop_hook.py",
                project_root,
                input_text=payload,
                env_overrides={
                    "ANTHROPIC_BASE_URL": base_url,
                    "ANTHROPIC_API_KEY": "secret-key",
                    "PATH": "",
                },
                use_fake_claude=False,
            )
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(result.returncode, 0)
        entries = [
            e for e in self._read_log_entries(project_root) if e.get("type") == "last_assistant_message_classified"
        ]
        self.assertEqual(entries[-1]["status"], "incomplete")
        review_events = [e for e in self._read_log_entries(project_root) if e.get("type") == "review_prompt_created"]
        self.assertEqual(review_events, [])

    def test_timeout_logs_error_and_existing_blocking_behavior_stays_intact(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir(parents=True, exist_ok=True)
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"lastAssistantMessageClassifierTimeoutSeconds": 0.01}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        server, base_url = start_classifier_server(label="complete", response_delay=0.2)
        try:
            payload = json.dumps({"last_assistant_message": "Not important for stop logic."})
            result = self.run_python(
                "hooks/stop_hook.py",
                project_root,
                input_text=payload,
                env_overrides={
                    "ANTHROPIC_BASE_URL": base_url,
                    "ANTHROPIC_API_KEY": "secret-key",
                    "PATH": "",
                },
                use_fake_claude=False,
                timeout=5,
            )
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(result.returncode, 2)
        entries = [
            e for e in self._read_log_entries(project_root) if e.get("type") == "last_assistant_message_classified"
        ]
        self.assertEqual(entries[-1]["status"], "error")
        self.assertEqual(entries[-1]["reason"], "http_timeout")
