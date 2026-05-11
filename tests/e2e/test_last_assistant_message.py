import json
import sys
from pathlib import Path

from claude_auto_review.stop.last_assistant_message import CLASSIFIER_MODEL
from tests.e2e.support import EndToEndTestCase, _ClassifierHandler

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from claude_auto_review.state.store_read import load_state


class EndToEndLastAssistantMessageTests(EndToEndTestCase):
    def test_stop_hook_e2e_logs_last_assistant_message_classification(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.track(project_root, "src/app.ts")
        server, base_url = self.start_classifier_server(label="complete")
        try:
            result = self.run_python(
                "hooks/stop_hook.py",
                project_root,
                input_text=json.dumps({"last_assistant_message": "Final answer delivered."}),
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
        self.assertEqual(len(_ClassifierHandler.requests), 1)
        self.assertEqual(_ClassifierHandler.requests[0]["path"], "/v1/messages")
        self.assertEqual(_ClassifierHandler.requests[0]["body"]["model"], CLASSIFIER_MODEL)

        state = load_state(project_root, "test-session")
        classifier_entries = [entry for entry in state if entry.get("type") == "assistant_message_classification"]
        self.assertEqual(len(classifier_entries), 1)
        self.assertEqual(classifier_entries[0]["status"], "complete")
        self.assertEqual(classifier_entries[0]["baseUrl"], base_url)

        log_entries = [entry for entry in self.read_log_entries(project_root) if entry.get("event") == "last_assistant_message_classified"]
        self.assertEqual(len(log_entries), 1)
        self.assertEqual(log_entries[0]["status"], "complete")
        self.assertEqual(log_entries[0]["reason"], "parsed_label")
        self.assertEqual(log_entries[0]["base_url"], base_url)
        self.assertNotIn("secret-key", json.dumps(log_entries[0]))
