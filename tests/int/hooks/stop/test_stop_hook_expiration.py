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
from tests.support import client_relpath  # noqa: E402


class TestStopHookExpiration(HookTestCase, unittest.TestCase):
    def test_stop_hook_does_not_clean_expired_reviews_for_payload_session_id(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")

        payload = json.dumps({"session_id": "payload-session", "file_path": "src/app.ts"})
        self.run_python("hooks/post_tool_use.py", project_root, payload, client_id="env-session")

        old_time = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        append_state_event(
            ReviewMetadata(
                timestamp=old_time,
                reviewId="expired-payload",
                reviewPath=client_relpath(project_root, "payload-session") + "/reviews/review-expired.md",
                status="pending",
                files=[ReviewFileRecord(file="src/app.ts", hash="testhash")],
                clientId="payload-session",
            ),
            project_root,
            client_id="payload-session",
        )

        stop = self.run_python(
            "hooks/stop_hook.py",
            project_root,
            payload,
            client_id="env-session",
            stdin_session_id_payload={"session_id": "payload-session"},
            env_overrides={"PATH": ""},
            use_fake_claude=False,
        )
        self.assertIn(stop.returncode, [0, 2], "Stop should not crash")

        state_after = load_state(project_root, client_id="payload-session")
        pending_ids = [e.reviewId for e in state_after if e.type == "review" and e.status == "pending"]
        self.assertIn("expired-payload", pending_ids)

    def test_pending_review_not_expired_is_used(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        stop1 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop1.returncode, 2)

        stop2 = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertEqual(stop2.returncode, 2)
        parsed = json.loads(stop2.stdout)
        self.assertIn("Review", parsed["systemMessage"])

    def test_pending_review_expired_is_skipped_but_not_cleaned_by_stop_hook(self):
        project_root = self.temp_project()
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        old_time = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        append_state_event(
            ReviewMetadata(
                timestamp=old_time,
                reviewId="rev-expired",
                reviewPath=client_relpath(project_root) + "/reviews/review-expired.md",
                status="pending",
                files=[ReviewFileRecord(file="src/app.ts", hash="testhash")],
                clientId="test-session",
            ),
            project_root,
            client_id="test-session",
        )

        state_before = load_state(project_root, client_id="test-session")
        expired_reviews = [e for e in state_before if e.type == "review" and e.status == "pending"]
        self.assertEqual(len(expired_reviews), 1, "Expired review should be in state")

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertIn(stop.returncode, [0, 2], "Stop should not crash")

        state_after = load_state(project_root, client_id="test-session")
        expired_ids = [e.reviewId for e in state_after if e.type == "review" and e.status == "pending"]
        self.assertIn("rev-expired", expired_ids, "Stop hook should not remove expired reviews")

    def test_pending_review_timeout_custom_setting_skip_only(self):
        project_root = self.temp_project()
        (project_root / ".claude").mkdir(parents=True, exist_ok=True)
        (project_root / ".claude" / "settings.json").write_text(
            json.dumps({"claude-auto-review": {"pendingReviewTimeoutHours": 0.01}}),
            encoding="utf-8",
        )
        (project_root / "src" / "app.ts").write_text("export const value = 1;\n", encoding="utf-8")
        self.run_python("hooks/post_tool_use.py", project_root, json.dumps({"file_path": "src/app.ts"}))

        old_time = (datetime.now().astimezone() - timedelta(minutes=1)).isoformat()
        append_state_event(
            ReviewMetadata(
                timestamp=old_time,
                reviewId="rev-custom-timeout",
                reviewPath=client_relpath(project_root) + "/reviews/review-custom.md",
                status="pending",
                files=[ReviewFileRecord(file="src/app.ts", hash="testhash")],
                clientId="test-session",
            ),
            project_root,
            client_id="test-session",
        )

        stop = self.run_python("hooks/stop_hook.py", project_root, env_overrides={"PATH": ""}, use_fake_claude=False)
        self.assertIn(stop.returncode, [0, 2], "Stop should not crash")

        state_after = load_state(project_root, client_id="test-session")
        expired_ids = [e.reviewId for e in state_after if e.type == "review" and e.status == "pending"]
        self.assertIn("rev-custom-timeout", expired_ids, "Stop hook should not remove expired reviews")

