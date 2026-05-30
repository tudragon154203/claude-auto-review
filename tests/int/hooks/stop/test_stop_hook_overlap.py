import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from claude_auto_review.state.models import ReviewFileRecord, ReviewMetadata  # noqa: E402
from claude_auto_review.state.store.read import load_state  # noqa: E402
from claude_auto_review.state.store.write import append_state_event  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402
from tests.support import client_dir  # noqa: E402


class TestStopHookOverlap(HookTestCase, unittest.TestCase):
    def test_stop_hook_prefers_higher_overlap_over_newer_review(self):
        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("export const b = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/a.ts"}))
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))

        edits = [e for e in load_state(project_root, "test-session") if e.type == "edit"]
        hash_a = [e.hash for e in edits if e.file == "src/a.ts"][-1]
        hash_b = [e.hash for e in edits if e.file == "src/b.ts"][-1]

        review_dir = client_dir(project_root) / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        path_high = review_dir / "review-high.md"
        path_new = review_dir / "review-newer.md"
        path_high.write_text("## Verdict\n\nPending.\n", encoding="utf-8")
        path_new.write_text("## Verdict\n\nPending.\n", encoding="utf-8")

        base = datetime.now().astimezone()
        ts_old = base.isoformat()
        ts_new = (base + timedelta(seconds=1)).isoformat()

        append_state_event(
            ReviewMetadata(
                timestamp=ts_old,
                reviewId="high-overlap",
                reviewPath=path_high.relative_to(project_root).as_posix(),
                status="pending",
                files=[
                    ReviewFileRecord(file="src/a.ts", hash=hash_a),
                    ReviewFileRecord(file="src/b.ts", hash=hash_b),
                ],
                clientId="test-session",
            ),
            project_root,
            client_id="test-session",
        )
        append_state_event(
            ReviewMetadata(
                timestamp=ts_new,
                reviewId="newer-low-overlap",
                reviewPath=path_new.relative_to(project_root).as_posix(),
                status="pending",
                files=[ReviewFileRecord(file="src/a.ts", hash=hash_a)],
                clientId="test-session",
            ),
            project_root,
            client_id="test-session",
        )

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop.returncode, 2)
        self.assertIn("Review high-overlap", json.loads(stop.stdout)["systemMessage"])

    def test_stop_hook_prefers_newest_pending_review_on_equal_overlap(self):
        project_root = self.temp_project()
        target = project_root / "src" / "app.ts"
        target.write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        current_hash = load_state(project_root, "test-session")[-1].hash
        review_dir = client_dir(project_root) / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        old_path = review_dir / "review-old.md"
        new_path = review_dir / "review-new.md"
        old_path.write_text("## Verdict\n\nPending.\n", encoding="utf-8")
        new_path.write_text("## Verdict\n\nPending.\n", encoding="utf-8")

        base = datetime.now().astimezone()
        ts_old = base.isoformat()
        ts_new = (base + timedelta(seconds=1)).isoformat()
        append_state_event(
            ReviewMetadata(
                timestamp=ts_old,
                reviewId="old",
                reviewPath=old_path.relative_to(project_root).as_posix(),
                status="pending",
                files=[ReviewFileRecord(file="src/app.ts", hash=current_hash)],
                clientId="test-session",
            ),
            project_root,
            client_id="test-session",
        )
        append_state_event(
            ReviewMetadata(
                timestamp=ts_new,
                reviewId="new",
                reviewPath=new_path.relative_to(project_root).as_posix(),
                status="pending",
                files=[ReviewFileRecord(file="src/app.ts", hash=current_hash)],
                clientId="test-session",
            ),
            project_root,
            client_id="test-session",
        )

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop.returncode, 2)
        self.assertIn("Review new", json.loads(stop.stdout)["systemMessage"])


if __name__ == "__main__":
    unittest.main()
