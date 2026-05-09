import os
import unittest
import unittest.mock as mock

from scripts.state import get_client_id

from tests.state.support import StateTestCase


class TestClientId(StateTestCase, unittest.TestCase):

    def test_get_client_id_uses_session_id_from_env(self):
        import unittest.mock as mock
        with mock.patch.dict(os.environ, {"CLAUDE_SESSION_ID": "fixed-session"}):
            result = get_client_id()
            self.assertEqual(result, "fixed-session")

