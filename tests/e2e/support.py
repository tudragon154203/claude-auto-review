import json
import socketserver
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path

from tests.support import SubprocessMixin, TempProjectMixin, make_classifier_handler


class _ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


class EndToEndTestCase(TempProjectMixin, SubprocessMixin, unittest.TestCase):
    def temp_project(self):
        temp_dir = tempfile.TemporaryDirectory(prefix="claude-auto-review-e2e-")
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name)
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

    def start_classifier_server(self, label="complete", payload=None):
        handler_cls = make_classifier_handler(label, response_payload=payload)
        server = _ThreadedHTTPServer(("127.0.0.1", 0), handler_cls)
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
