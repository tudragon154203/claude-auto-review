import json
import tempfile
from datetime import datetime
from pathlib import Path

from tests.int.support import IntegrationTestCase, REPO_ROOT, _FakeResponse
from tests.support import client_dir

from claude_auto_review.paths.path_utils import get_state_path
from claude_auto_review.runtime.client_dirs import client_state_path
from claude_auto_review.runtime.events import log_event
from claude_auto_review.runtime.cleanup.session import cancel_runtime
from claude_auto_review.runtime.setup import ensure_client_runtime, ensure_project_settings, ensure_runtime
from claude_auto_review.config.io import load_settings
from claude_auto_review.config.models import DEFAULT_TIMEOUT_SECONDS, PluginSettings
from claude_auto_review.state.store.read import consecutive_stop_blocks, load_state
from claude_auto_review.state.models import EditRecord
from claude_auto_review.state.store.write import append_state_event
from claude_auto_review.stop.classifier.core.last_assistant_message import classify_last_assistant_message
from claude_auto_review.stop.orchestration.core.context import RuntimeContext


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
        log_path = get_state_path(project_root)

        self.assertTrue(log_path.exists())
        content = log_path.read_text(encoding="utf-8")
        entry = json.loads(content.strip().split("\n")[-1])
        self.assertEqual(entry["type"], "test_event")
        self.assertEqual(entry["foo"], "bar")
        self.assertEqual(entry["count"], 42)
        self.assertIn("timestamp", entry)
        self.assertFalse(entry["timestamp"].endswith("Z"))
        self.assertNotIn("clientId", entry)

    def test_log_event_includes_client_id_when_provided(self):
        project_root = self.temp_project()
        ensure_client_runtime(project_root, "session-abc")

        log_event(project_root, "test_event", client_id="session-abc", foo="bar")
        log_path = client_state_path(project_root, "session-abc")

        self.assertTrue(log_path.exists())
        content = log_path.read_text(encoding="utf-8")
        entry = json.loads(content.strip().split("\n")[-1])
        self.assertEqual(entry["type"], "test_event")
        self.assertEqual(entry["clientId"], "session-abc")
        self.assertEqual(entry["foo"], "bar")

    def test_ensure_project_settings_preserves_user_values(self):
        project_root = self.temp_project()

        ensure_project_settings(project_root)
        settings = load_settings(project_root)
        self.assertTrue(settings.enabled)

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
        self.assertFalse(settings.enabled)
        self.assertEqual(settings.extras["customKey"], "value")
        self.assertEqual(settings.reviewer_timeout_seconds, 600)
        self.assertTrue(settings.last_assistant_message_classifier_enabled)
        self.assertEqual(settings.last_assistant_message_classifier_timeout_seconds, DEFAULT_TIMEOUT_SECONDS)

    def test_classifier_appends_separate_state_entry_and_log(self):
        project_root = self.temp_project()
        client_id = "classifier-integration"
        ensure_client_runtime(project_root, client_id)

        result = classify_last_assistant_message(
            RuntimeContext(
                project_root=project_root,
                client_id=client_id,
                settings=PluginSettings(
                    last_assistant_message_classifier_enabled=True,
                    last_assistant_message_classifier_timeout_seconds=10,
                ),
                payload={"last_assistant_message": "Final answer."},
            ),
            env={
                "ANTHROPIC_BASE_URL": "http://127.0.0.1:13456",
                "ANTHROPIC_API_KEY": "secret-key",
            },
            urlopen=lambda req, timeout: _FakeResponse({"content": [{"type": "text", "text": "complete"}]}),
        )

        self.assertEqual(result.status, "complete")
        state = load_state(project_root, client_id)
        self.assertEqual(state[-1].type, "last_assistant_message_classified")
        self.assertEqual(state[-1].status, "complete")
        self.assertEqual(consecutive_stop_blocks(state), 0)
        log_entry = json.loads((client_state_path(project_root, client_id)).read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(log_entry["type"], "last_assistant_message_classified")
        self.assertNotIn("secret-key", json.dumps(log_entry))

    def test_cancel_runtime_removes_client_artifacts(self):
        project_root = self.temp_project()
        client_id = "cleanup-test"
        ensure_client_runtime(project_root, client_id)

        append_state_event(
            EditRecord(
                timestamp=datetime.now().astimezone().isoformat(),
                file="x.ts",
                hash="deadbeef",
                reviewed=False,
            ),
            project_root,
            client_id=client_id,
        )

        client_dir_path = client_dir(project_root, client_id)
        self.assertTrue(client_dir_path.exists())

        cancel_runtime(project_root, client_id=client_id)
        self.assertFalse(client_dir_path.exists())

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

