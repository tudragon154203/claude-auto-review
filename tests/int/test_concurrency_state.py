from tests.int.support import ClientIsolationTestCase

from claude_auto_review.paths import client_state_path
from claude_auto_review.state.models import EditRecord
from claude_auto_review.state.store_read import get_unreviewed_files, load_state, was_hash_reviewed
from claude_auto_review.state.store_write import append_state, mark_files_reviewed


class ConcurrencyStateTests(ClientIsolationTestCase):
    def test_two_clients_do_not_share_state(self):
        project_root = self.temp_project()
        client_a = "client-alpha"
        client_b = "client-beta"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        append_state(EditRecord(timestamp="2026-05-09T10:00:00+07:00", file="src/a.ts", hash="aaaa1111", reviewed=False), project_root, client_id=client_a)
        append_state(EditRecord(timestamp="2026-05-09T11:00:00+07:00", file="src/b.ts", hash="bbbb2222", reviewed=False), project_root, client_id=client_b)

        state_a = load_state(project_root, client_a)
        state_b = load_state(project_root, client_b)

        self.assertEqual(len(state_a), 1)
        self.assertEqual(state_a[0].file, "src/a.ts")
        self.assertEqual(len(state_b), 1)
        self.assertEqual(state_b[0].file, "src/b.ts")

    def test_unreviewed_files_scoped_to_client(self):
        project_root = self.temp_project()
        client_a = "client-a"
        client_b = "client-b"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        append_state(EditRecord(timestamp="2026-05-09T14:00:00+07:00", file="common.ts", hash="aaa", reviewed=False), project_root, client_id=client_a)
        append_state(EditRecord(timestamp="2026-05-09T14:00:00+07:00", file="common.ts", hash="bbb", reviewed=True, reviewId="rev-b"), project_root, client_id=client_b)

        unreviewed_a = get_unreviewed_files(load_state(project_root, client_a))
        unreviewed_b = get_unreviewed_files(load_state(project_root, client_b))

        self.assertEqual(len(unreviewed_a), 1)
        self.assertEqual(unreviewed_a[0].file, "common.ts")
        self.assertEqual(unreviewed_a[0].hash, "aaa")
        self.assertEqual(len(unreviewed_b), 0)

    def test_marking_reviewed_is_isolated(self):
        project_root = self.temp_project()
        client_a = "client-a"
        client_b = "client-b"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        entry = EditRecord(timestamp="2026-05-09T15:00:00+07:00", file="isolated.ts", hash="deadbeef", reviewed=False)
        append_state(entry, project_root, client_id=client_a)
        append_state(entry, project_root, client_id=client_b)

        self.assertFalse(was_hash_reviewed(load_state(project_root, client_a), "isolated.ts", "deadbeef"))
        self.assertFalse(was_hash_reviewed(load_state(project_root, client_b), "isolated.ts", "deadbeef"))

        mark_files_reviewed([entry], "rev-a", project_root, client_id=client_a)

        self.assertTrue(was_hash_reviewed(load_state(project_root, client_a), "isolated.ts", "deadbeef"))
        self.assertFalse(was_hash_reviewed(load_state(project_root, client_b), "isolated.ts", "deadbeef"))

    def test_client_state_files_are_separate(self):
        project_root = self.temp_project()
        client_a = "client-a"
        client_b = "client-b"
        self.ensure_client(project_root, client_a)
        self.ensure_client(project_root, client_b)

        append_state(EditRecord(timestamp="2026-05-09T09:00:00+07:00", file="a.ts", hash="aaa", reviewed=False), project_root, client_id=client_a)
        append_state(EditRecord(timestamp="2026-05-09T09:30:00+07:00", file="b.ts", hash="bbb", reviewed=False), project_root, client_id=client_b)

        path_a = client_state_path(project_root, client_a)
        path_b = client_state_path(project_root, client_b)

        self.assertTrue(path_a.exists())
        self.assertTrue(path_b.exists())
        self.assertNotEqual(path_a, path_b)

    def test_multiple_edits_ordered_per_client(self):
        project_root = self.temp_project()
        client_a = "client-a"
        self.ensure_client(project_root, client_a)

        append_state(EditRecord(timestamp="2026-05-09T16:00:00+07:00", file="evolving.ts", hash="v1", reviewed=False), project_root, client_id=client_a)
        append_state(EditRecord(timestamp="2026-05-09T17:00:00+07:00", file="evolving.ts", hash="v2", reviewed=False), project_root, client_id=client_a)
        append_state(EditRecord(timestamp="2026-05-09T18:00:00+07:00", file="evolving.ts", hash="v3", reviewed=True, reviewId="rev"), project_root, client_id=client_a)
        append_state(EditRecord(timestamp="2026-05-09T19:00:00+07:00", file="evolving.ts", hash="v4", reviewed=False), project_root, client_id=client_a)

        unreviewed = get_unreviewed_files(load_state(project_root, client_a))
        self.assertEqual(len(unreviewed), 1)
        self.assertEqual(unreviewed[0].file, "evolving.ts")
        self.assertEqual(unreviewed[0].hash, "v4")
