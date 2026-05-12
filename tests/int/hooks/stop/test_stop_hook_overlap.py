import json
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from claude_auto_review.state.store_read import load_state  # noqa: E402
from claude_auto_review.state.store_write import append_state  # noqa: E402
from tests.int.hooks.support import HookTestCase  # noqa: E402


class TestStopHookOverlap(HookTestCase, unittest.TestCase):
    def test_stop_hook_prefers_higher_overlap_over_newer_review(self):
        project_root = self.temp_project()
        (project_root / "src" / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")
        (project_root / "src" / "b.ts").write_text("export const b = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/a.ts"}))
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))

        edits = [e for e in load_state(project_root, "test-session") if e.get("type") == "edit"]
        hash_a = [e["hash"] for e in edits if e.get("file") == "src/a.ts"][-1]
        hash_b = [e["hash"] for e in edits if e.get("file") == "src/b.ts"][-1]

        review_dir = project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        path_high = review_dir / "review-high.md"
        path_new = review_dir / "review-newer.md"
        path_high.write_text("## Verdict\n\nPending.\n", encoding="utf-8")
        path_new.write_text("## Verdict\n\nPending.\n", encoding="utf-8")

        base = datetime.now().astimezone()
        ts_old = base.isoformat()
        ts_new = (base + timedelta(seconds=1)).isoformat()

        append_state(
            {
                "type": "review",
                "reviewId": "high-overlap",
                "reviewPath": str(path_high),
                "timestamp": ts_old,
                "status": "pending",
                "files": [
                    {"file": "src/a.ts", "hash": hash_a},
                    {"file": "src/b.ts", "hash": hash_b},
                ],
            },
            project_root,
            client_id="test-session",
        )
        append_state(
            {
                "type": "review",
                "reviewId": "newer-low-overlap",
                "reviewPath": str(path_new),
                "timestamp": ts_new,
                "status": "pending",
                "files": [{"file": "src/a.ts", "hash": hash_a}],
            },
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

        current_hash = load_state(project_root, "test-session")[-1]["hash"]
        review_dir = project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        old_path = review_dir / "review-old.md"
        new_path = review_dir / "review-new.md"
        old_path.write_text("## Verdict\n\nPending.\n", encoding="utf-8")
        new_path.write_text("## Verdict\n\nPending.\n", encoding="utf-8")

        base = datetime.now().astimezone()
        ts_old = base.isoformat()
        ts_new = (base + timedelta(seconds=1)).isoformat()
        append_state(
            {
                "type": "review",
                "reviewId": "old",
                "reviewPath": str(old_path),
                "timestamp": ts_old,
                "status": "pending",
                "files": [{"file": "src/app.ts", "hash": current_hash}],
            },
            project_root,
            client_id="test-session",
        )
        append_state(
            {
                "type": "review",
                "reviewId": "new",
                "reviewPath": str(new_path),
                "timestamp": ts_new,
                "status": "pending",
                "files": [{"file": "src/app.ts", "hash": current_hash}],
            },
            project_root,
            client_id="test-session",
        )

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop.returncode, 2)
        self.assertIn("Review new", json.loads(stop.stdout)["systemMessage"])

    def test_stop_hook_rebuilds_review_when_existing_review_is_partial_stale_match(self):
        project_root = self.temp_project()
        file_a = project_root / "src" / "a.ts"
        file_b = project_root / "src" / "b.ts"
        file_a.write_text("export const a = 1;\n", encoding="utf-8")
        file_b.write_text("export const b = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/a.ts"}))
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/b.ts"}))

        edits = [e for e in load_state(project_root, "test-session") if e.get("type") == "edit"]
        old_hash_a = [e["hash"] for e in edits if e.get("file") == "src/a.ts"][-1]
        hash_b = [e["hash"] for e in edits if e.get("file") == "src/b.ts"][-1]

        review_dir = project_root / ".claude" / "claude-auto-review" / "clients" / "client-test-session" / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        stale_path = review_dir / "review-stale.md"
        stale_path.write_text("## Verdict\n\nNot clean - fix a.ts.\n", encoding="utf-8")
        append_state(
            {
                "type": "review",
                "reviewId": "stale",
                "reviewPath": str(stale_path),
                "timestamp": datetime.now().astimezone().isoformat(),
                "status": "pending",
                "files": [{"file": "src/a.ts", "hash": old_hash_a}, {"file": "src/b.ts", "hash": hash_b}],
            },
            project_root,
            client_id="test-session",
        )

        file_a.write_text("export const a = 2;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/a.ts"}))
        latest_hash_a = load_state(project_root, "test-session")[-1]["hash"]

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)

        self.assertEqual(stop.returncode, 2)
        self.assertNotIn("Review stale found issues", json.loads(stop.stdout)["systemMessage"])
        reviews = [e for e in load_state(project_root, "test-session") if e.get("type") == "review"]
        self.assertEqual(len(reviews), 2)
        latest_review = reviews[-1]
        self.assertNotEqual(latest_review["reviewId"], "stale")
        self.assertIn({"file": "src/a.ts", "hash": latest_hash_a}, latest_review["files"])
        self.assertIn({"file": "src/b.ts", "hash": hash_b}, latest_review["files"])
