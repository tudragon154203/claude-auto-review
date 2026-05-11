import json
import socketserver
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from tests.support import SubprocessMixin, TempProjectMixin


class _ClassifierHandler(BaseHTTPRequestHandler):
    response_label = "complete"
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


class EndToEndTestCase(TempProjectMixin, SubprocessMixin, unittest.TestCase):
    def temp_project(self):
        project_root = Path(tempfile.mkdtemp(prefix="claude-auto-review-e2e-"))
        (project_root / "src").mkdir(parents=True)
        return project_root

    def track(self, project_root, file_path, client_id="test-session"):
        return self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            json.dumps({"tool_input": {"file_path": file_path}}),
            client_id=client_id,
        )

    def stop(self, project_root, client_id="test-session", use_fake_claude=None, env_overrides=None):
        return self.run_python(
            "hooks/stop_hook.py",
            project_root,
            client_id=client_id,
            use_fake_claude=use_fake_claude,
            env_overrides=env_overrides,
        )

    def review(self, project_root, client_id="test-session"):
        return self.run_python("claude_auto_review/review/prompt.py", project_root, client_id=client_id)

    def runtime_script(self, project_root, script_name):
        return project_root / ".claude" / "claude-auto-review" / "scripts" / script_name

    def read_log_entries(self, project_root):
        log_path = project_root / ".claude" / "claude-auto-review" / "claude-auto-review.log"
        return [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def start_classifier_server(self, label="complete"):
        _ClassifierHandler.response_label = label
        _ClassifierHandler.requests = []
        server = _ThreadedHTTPServer(("127.0.0.1", 0), _ClassifierHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, f"http://127.0.0.1:{server.server_port}"

    def complete_review(self, project_root, verdict="Clean - no issues found.", client_id="test-session"):
        review_dir = project_root / ".claude" / "claude-auto-review" / "clients" / f"client-{client_id}" / "reviews"
        review_path = sorted(review_dir.glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        content = content.replace(
            "Pending. Claude must complete this review from",
            "Completed review from",
        )
        content = content.replace("Pending.", verdict)
        review_path.write_text(content, encoding="utf-8", newline="\n")
        return review_path
