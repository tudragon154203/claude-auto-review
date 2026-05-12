import json
import tempfile
from datetime import datetime
from pathlib import Path

from tests.int.support import IntegrationTestCase, REPO_ROOT, _FakeResponse

from claude_auto_review.paths import get_log_path
from claude_auto_review.runtime.cleanup import cancel_runtime
from claude_auto_review.runtime.setup import ensure_client_runtime, ensure_project_settings, ensure_runtime
from claude_auto_review.settings import DEFAULT_SETTINGS, DEFAULT_TIMEOUT_SECONDS, load_settings
from claude_auto_review.state.store_read import consecutive_stop_blocks, load_state
from claude_auto_review.state.store_write import append_state, log_event
from claude_auto_review.stop.classifier.last_assistant_message import classify_last_assistant_message


class IntegrationRuntimeTests(IntegrationTestCase):
    def test_ensure_runtime_creates_complete_structure(self):
        project_root = self.temp_project()

        result = ensure_runtime(project_root, REPO_ROOT)

        self.assertTrue(result["base_dir"].exists())
        self.assertTrue(result["rules_path"].exists())
        self.assertTrue(result["state_path"].parent.exists())
        self.assertTrue(result["log_path"].parent.exists())
        self.assertFalse((project_root / ".claude" / "claude-auto-review" / "state.jsonl").exists())

    def test_log_event_writes_formatted_entries(self):
        project_root = self.temp_project()

        log_event(project_root, "test_event", foo="bar", count=42)
        log_path = get_log_path(project_root)

        self.assertTrue(log_path.exists())
        content = log_path.read_text(encoding="utf-8")
        entry = json.loads(content.strip().split("\n")[-1])
        self.assertEqual(entry["type"], "test_event")
        self.assertEqual(entry["foo"], "bar")
        self.assertEqual(entry["count"], 42)
        self.assertIn("timestamp", entry)
        self.assertFalse(entry["timestamp"].endswith("Z"))

    def test_ensure_project_settings_preserves_user_values(self):
        project_root = self.temp_project()

        ensure_project_settings(project_root)
        settings = load_settings(project_root)
        self.assertTrue(settings["enabled"])

        settings_file = project_root / ".claude" / "settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "claude-auto-review": {
                        "enabled": False,
                        "customKey": "value",
                    },
                }
            ),
            encoding="utf-8",
        )

        ensure_project_settings(project_root)
        settings = load_settings(project_root)
        self.assertFalse(settings["enabled"])
        self.assertEqual(settings["customKey"], "value")
        self.assertEqual(settings["reviewerTimeoutSeconds"], 600)
        self.assertTrue(settings["lastAssistantMessageClassifierEnabled"])
        self.assertEqual(settings["lastAssistantMessageClassifierTimeoutSeconds"], DEFAULT_TIMEOUT_SECONDS)

    def test_classifier_appends_separate_state_entry_and_log(self):
        project_root = self.temp_project()
        client_id = "classifier-integration"
        ensure_client_runtime(project_root, client_id)

        result = classify_last_assistant_message(
            project_root,
            client_id,
            {"last_assistant_message": "Final answer."},
            {"lastAssistantMessageClassifierEnabled": True, "lastAssistantMessageClassifierTimeoutSeconds": 10},
            env={
                "ANTHROPIC_BASE_URL": "http://127.0.0.1:13456",
                "ANTHROPIC_API_KEY": "secret-key",
            },
            urlopen=lambda req, timeout: _FakeResponse({"content": [{"type": "text", "text": "complete"}]}),
        )

        self.assertEqual(result.status, "complete")
        state = load_state(project_root, client_id)
        self.assertEqual(state[-1]["type"], "last_assistant_message_classified")
        self.assertEqual(state[-1]["status"], "complete")
        self.assertEqual(consecutive_stop_blocks(state), 0)
        log_entry = json.loads(get_log_path(project_root).read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(log_entry["type"], "last_assistant_message_classified")
        self.assertNotIn("secret-key", json.dumps(log_entry))

    def test_cancel_runtime_removes_client_artifacts(self):
        project_root = self.temp_project()
        client_id = "cleanup-test"
        ensure_client_runtime(project_root, client_id)

        append_state(
            {
                "type": "edit",
                "file": "x.ts",
                "hash": "deadbeef",
                "timestamp": datetime.now().astimezone().isoformat(),
                "reviewed": False,
            },
            project_root,
            client_id=client_id,
        )

        client_dir = project_root / ".claude" / "claude-auto-review" / "clients" / f"client-{client_id}"
        self.assertTrue(client_dir.exists())

        cancel_runtime(project_root, client_id=client_id)
        self.assertFalse(client_dir.exists())

    def test_ensure_runtime_is_idempotent(self):
        project_root = self.temp_project()
        result1 = ensure_runtime(project_root, REPO_ROOT)
        result2 = ensure_runtime(project_root, REPO_ROOT)
        self.assertEqual(result1["rules_path"].read_text(encoding="utf-8"), result2["rules_path"].read_text(encoding="utf-8"))

    def test_log_event_error_silent(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-log-"))
        nonexistent = project_root / "nope" / "deep"
        log_event(nonexistent, "should_not_crash")
        self.assertTrue(True)
