import json

from claude_auto_review.config.models import DEFAULT_CLASSIFIER_MODEL
from claude_auto_review.state.store.read import load_state
from tests.e2e.support import EndToEndTestCase


class EndToEndLastAssistantMessageTests(EndToEndTestCase):
    def test_stop_hook_e2e_logs_last_last_assistant_message_classified_invalid_label(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.track(project_root, "src/app.ts")
        classifier_response = {
            "id": "gen-test",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "thinking",
                    "thinking": "\nThe user wants me to classify whether the assistant message is a true completion or",
                }
            ],
            "model": DEFAULT_CLASSIFIER_MODEL,
            "stop_reason": "max_tokens",
            "stop_sequence": None,
            "usage": {"input_tokens": 286, "output_tokens": 16},
        }
        server, base_url = self.start_classifier_server(payload=classifier_response)
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
        self.assertEqual(len(server.requests), 1)
        self.assertEqual(server.requests[0]["path"], "/v1/messages")
        self.assertEqual(server.requests[0]["body"]["model"], DEFAULT_CLASSIFIER_MODEL)

        state = load_state(project_root, "test-session")
        classifier_entries = [entry for entry in state if entry.type == "last_assistant_message_classified"]
        self.assertEqual(len(classifier_entries), 1)
        self.assertEqual(classifier_entries[0].status, "unknown")
        self.assertEqual(classifier_entries[0].reason, "invalid_label")
        self.assertEqual(classifier_entries[0].baseUrl, base_url)

        log_entries = [entry for entry in self.read_log_entries(project_root) if entry.get("type") == "last_assistant_message_classified"]
        self.assertEqual(len(log_entries), 1)
        self.assertEqual(log_entries[0]["status"], "unknown")
        self.assertEqual(log_entries[0]["reason"], "invalid_label")
        self.assertEqual(log_entries[0]["baseUrl"], base_url)
        self.assertEqual(json.loads(log_entries[0]["debugResponse"]), classifier_response)
        self.assertNotIn("secret-key", json.dumps(log_entries[0]))
