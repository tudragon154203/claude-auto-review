import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from tests.int.hooks.support import HookTestCase  # noqa: E402
from tests.support import client_dir  # noqa: E402


class TestStopHookClassifier(HookTestCase, unittest.TestCase):
    def _read_log_entries(self, project_root):
        log_path = client_dir(project_root) / "state.jsonl"
        return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_stop_hook_skips_classifier_when_disabled(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir(parents=True, exist_ok=True)
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"lastAssistantMessageClassifierEnabled": False}}),
            encoding="utf-8",
        )

        payload = json.dumps({"last_assistant_message": "This should be ignored for classification."})
        stop = self.run_python("hooks/stop_hook.py", project_root, input_text=payload, use_fake_claude=False)
        self.assertEqual(stop.returncode, 0)
        log_path = client_dir(project_root) / "state.jsonl"
        if log_path.exists():
            events = [
                e for e in self._read_log_entries(project_root) if e.get("type") == "last_assistant_message_classified"
            ]
            self.assertEqual(events, [])
        else:
            self.assertFalse(log_path.exists())

    def test_stop_hook_logs_skipped_classifier_for_missing_message(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        stop = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            input_text=json.dumps({"session_id": "test-session"}),
            env_overrides={"PATH": ""},
            use_fake_claude=False,
        )
        self.assertEqual(stop.returncode, 2)
        events = [
            e for e in self._read_log_entries(project_root) if e.get("type") == "last_assistant_message_classified"
        ]
        self.assertEqual(events[-1]["status"], "skipped")
        self.assertEqual(events[-1]["reason"], "missing_message")

    def test_stop_hook_logs_missing_api_key_without_affecting_clean_stop(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        payload = json.dumps({"last_assistant_message": "Looks final."})
        stop = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            input_text=payload,
            env_overrides={"ANTHROPIC_BASE_URL": "http://127.0.0.1:13456", "ANTHROPIC_API_KEY": "", "PATH": ""},
            use_fake_claude=False,
        )
        self.assertEqual(stop.returncode, 2)
        events = [
            e for e in self._read_log_entries(project_root) if e.get("type") == "last_assistant_message_classified"
        ]
        self.assertEqual(events[-1]["status"], "error")
        self.assertEqual(events[-1]["reason"], "missing_api_key")
        self.assertNotIn("x-api-key", json.dumps(events[-1]).lower())
