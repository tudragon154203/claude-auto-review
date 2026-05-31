import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from claude_auto_review.state.models import EditRecord, ReviewFileRecord, ReviewMetadata  # noqa: E402
from claude_auto_review.state.store.read import load_state  # noqa: E402
from claude_auto_review.state.store.write import append_state_event  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402
from tests.support_paths import client_dir  # noqa: E402


class TestStopHookOverlapRebuild(HookTestCase, unittest.TestCase):
    def test_stop_hook_rebuilds_review_when_existing_review_is_partial_stale_match(self):
        project_root = self.temp_project()
        file_a = project_root / "src" / "a.ts"
        file_b = project_root / "src" / "b.ts"
        file_a.write_text("export const a = 1;\n", encoding="utf-8")
        file_b.write_text("export const b = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/a.ts"}))
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))

        edits = [e for e in load_state(project_root, "test-session") if e.type == "edit"]
        old_hash_a = [e.hash for e in edits if e.file == "src/a.ts"][-1]
        hash_b = [e.hash for e in edits if e.file == "src/b.ts"][-1]

        review_dir = client_dir(project_root) / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        stale_path = review_dir / "review-stale.md"
        stale_path.write_text("## Verdict\n\nNot clean - fix a.ts.\n", encoding="utf-8")
        append_state_event(
            ReviewMetadata(
                timestamp=datetime.now().astimezone().isoformat(),
                reviewId="stale",
                reviewPath=stale_path.relative_to(project_root).as_posix(),
                status="pending",
                files=[
                    ReviewFileRecord(file="src/a.ts", hash=old_hash_a),
                    ReviewFileRecord(file="src/b.ts", hash=hash_b),
                ],
                clientId="test-session",
            ),
            project_root,
            client_id="test-session",
        )

        file_a.write_text("export const a = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/a.ts"}))
        latest_hash_a = load_state(project_root, "test-session")[-1].hash

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)

        self.assertEqual(stop.returncode, 2)
        self.assertNotIn("Review stale found issues", json.loads(stop.stdout)["systemMessage"])
        reviews = [e for e in load_state(project_root, "test-session") if e.type == "review"]
        self.assertEqual(len(reviews), 2)
        latest_review = reviews[-1]
        self.assertNotEqual(latest_review.reviewId, "stale")
        self.assertIn(ReviewFileRecord(file="src/a.ts", hash=latest_hash_a), latest_review.files)
        self.assertIn(ReviewFileRecord(file="src/b.ts", hash=hash_b), latest_review.files)

    def test_stop_hook_rebuilds_review_when_next_pass_unreviewed_set_shrinks(self):
        project_root = self.temp_project()
        file_a = project_root / "src" / "a.ts"
        file_b = project_root / "src" / "b.ts"
        file_a.write_text("export const a = 1;\n", encoding="utf-8")
        file_b.write_text("export const b = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/a.ts"}))
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))

        first_stop = self.run_python(
            "hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False
        )
        self.assertEqual(first_stop.returncode, 2)

        state = load_state(project_root, "test-session")
        current_entries = {entry.file: entry for entry in state if entry.type == "edit" and not entry.reviewed}
        append_state_event(
            EditRecord(
                timestamp=datetime.now().astimezone().isoformat(),
                file="src/b.ts",
                hash=current_entries["src/b.ts"].hash,
                reviewed=True,
                reviewId="manual-pass-1",
            ),
            project_root,
            client_id="test-session",
        )

        second_stop = self.run_python(
            "hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False
        )

        self.assertEqual(second_stop.returncode, 2)
        reviews = [e for e in load_state(project_root, "test-session") if e.type == "review"]
        self.assertEqual(len(reviews), 2)
        latest_review = reviews[-1]
        self.assertEqual(
            latest_review.files, [ReviewFileRecord(file="src/a.ts", hash=current_entries["src/a.ts"].hash)]
        )
        self.assertIn("Review " + latest_review.reviewId, json.loads(second_stop.stdout)["systemMessage"])


if __name__ == "__main__":
    unittest.main()
