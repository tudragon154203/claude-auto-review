import json
import sys
import unittest
from pathlib import Path

from tests.support import TempProjectMixin

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.runtime.setup import ensure_client_runtime


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class IntegrationTestCase(TempProjectMixin, unittest.TestCase):
    pass


class ClientIsolationTestCase(TempProjectMixin, unittest.TestCase):
    def ensure_client(self, project_root, client_id):
        ensure_client_runtime(project_root, client_id)
        return project_root
