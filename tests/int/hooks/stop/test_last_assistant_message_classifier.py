import json
import socketserver
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from claude_auto_review.stop.last_assistant_message import CLASSIFIER_MODEL
from tests.int.hooks.support import HookTestCase


class _ClassifierHandler(BaseHTTPRequestHandler):
    response_label = "complete"
    response_delay = 0
    requests = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
        type(self).requests.append(
            {
                "path": self.path,
                "headers": dict(self.headers.items()),
                "body": json.loads(body),
            }
        )
        if type(self).response_delay:
            time.sleep(type(self).response_delay)
        payload = {"content": [{"type": "text", "text": type(self).response_label}]}
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except OSError:
            pass

    def log_message(self, fmt, *args):
        return


class _ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


class TestLastAssistantMessageClassifierHook(HookTestCase, unittest.TestCase):
    def _start_server(self, label="complete", delay=0):
        _ClassifierHandler.response_label = label
        _ClassifierHandler.response_delay = delay
        _ClassifierHandler.requests = []
        server = _ThreadedHTTPServer(("127.0.0.1", 0), _ClassifierHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, f"http://127.0.0.1:{server.server_port}"

    def _read_log_entries(self, project_root):
        log_path = project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log"
        return [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_stop_hook_logs_complete_classification_without_changing_clean_stop(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        server, base_url = self._start_server(label="complete")
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
        self.assertEqual(len(_ClassifierHandler.requests), 1)
        self.assertEqual(_ClassifierHandler.requests[0]["body"]["model"], CLASSIFIER_MODEL)
        entries = [e for e in self._read_log_entries(project_root) if e.get("event") == "last_assistant_message_classified"]
        self.assertEqual(entries[-1]["status"], "complete")
        self.assertEqual(entries[-1]["reason"], "parsed_label")
        self.assertEqual(entries[-1]["base_url"], base_url)
        self.assertNotIn("secret-key", json.dumps(entries[-1]))

    def test_stop_hook_logs_incomplete_classification(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))
        server, base_url = self._start_server(label="incomplete")
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

        self.assertEqual(result.returncode, 2)
        entries = [e for e in self._read_log_entries(project_root) if e.get("event") == "last_assistant_message_classified"]
        self.assertEqual(entries[-1]["status"], "incomplete")

    def test_timeout_logs_error_and_existing_blocking_behavior_stays_intact(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir(parents=True, exist_ok=True)
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"lastAssistantMessageClassifierTimeoutSeconds": 0.01}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        server, base_url = self._start_server(label="complete", delay=0.2)
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
        entries = [e for e in self._read_log_entries(project_root) if e.get("event") == "last_assistant_message_classified"]
        self.assertEqual(entries[-1]["status"], "error")
        self.assertEqual(entries[-1]["reason"], "http_timeout")
