import json
import sys
from pathlib import Path

from tests.e2e.support import EndToEndTestCase

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from claude_auto_review.state.store_read import load_state


class EndToEndFileDeletionTests(EndToEndTestCase):
    def test_deleted_file_is_tracked_with_deleted_hash(self):
        project_root = self.temp_project()
        self.track(project_root, "src/app.ts")

        payload = {"tool_name": "Remove", "tool_input": {"file_path": "src/app.ts"}}
        result = self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            json.dumps(payload),
        )

        self.assertEqual(result.returncode, 0)
        state = load_state(project_root, "test-session")
        self.assertEqual(len(state), 2)
        self.assertEqual(state[1].file, "src/app.ts")
        self.assertEqual(state[1].hash, "__deleted__")
        self.assertTrue(state[1].deleted)

    def test_deleted_file_allows_stop(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        self.track(project_root, "src/app.ts", client_id="delete-test")

        # Actually delete the file from disk
        (project_root / "src" / "app.ts").unlink()

        # Track the deletion
        payload = {"tool_name": "Remove", "tool_input": {"file_path": "src/app.ts"}}
        self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            json.dumps(payload),
            client_id="delete-test",
        )

        stop_result = self.stop(project_root, client_id="delete-test", use_fake_claude=False, env_overrides={"PATH": ""})
        self.assertEqual(stop_result.returncode, 0, "Deleted files should allow stop")
