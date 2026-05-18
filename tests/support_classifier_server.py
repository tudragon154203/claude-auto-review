import json
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def make_classifier_handler(response_label="complete", response_delay=0, response_payload=None):
    """Return an isolated HTTP handler class for last-assistant-message tests."""
    captured_requests = []

    class _ClassifierHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
            captured_requests.append(
                {
                    "path": self.path,
                    "headers": dict(self.headers.items()),
                    "body": json.loads(body),
                }
            )
            if response_delay:
                time.sleep(response_delay)
            payload = response_payload
            if payload is None:
                payload = {"content": [{"type": "text", "text": response_label}]}
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except OSError:
                return

        def log_message(self, fmt, *args):
            return

    _ClassifierHandler.requests = captured_requests
    return _ClassifierHandler


class _ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


def start_classifier_server(label, response_payload=None, response_delay=0):
    """Start a mock classifier HTTP server; return (server, base_url)."""
    handler_cls = make_classifier_handler(label, response_payload=response_payload, response_delay=response_delay)
    server = _ThreadedHTTPServer(("127.0.0.1", 0), handler_cls)
    server.requests = handler_cls.requests
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"
