import json
from datetime import datetime, timedelta
from pathlib import Path

from tests.e2e.support import EndToEndTestCase
from claude_auto_review.paths import client_state_path, get_log_path, local_now_iso


_CLEANUP_SCRIPT = (
    "import json, sys; "
    "sys.path.insert(0, sys.argv[1]); "
    "from claude_auto_review.runtime.cleanup import cleanup_expired_pending_reviews; "
    "removed = cleanup_expired_pending_reviews(sys.argv[2], client_id=sys.argv[3]); "
    "print(removed)"
)


class ExpiredReviewCleanupE2ETests(EndToEndTestCase):
    def _run_cleanup(self, project_root, client_id):
        repo_root = str(Path(__file__).resolve().parents[2])
        return self.run_python(
            "-c",
            project_root,
            env_overrides={"PYTHONPATH": repo_root},
            use_fake_claude=False,
            extra_args=[_CLEANUP_SCRIPT, repo_root, str(project_root), client_id],
        )

    def _write_settings(self, project_root, timeout_hours=1):
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps({"claude-auto-review": {"pendingReviewTimeoutHours": timeout_hours}}),
            encoding="utf-8",
        )

    def test_expired_review_removed_fresh_kept(self):
        project_root = self.temp_project()
        client_id = "cleanup-expired"
        (project_root / "src" / "test.ts").write_text("const x = 1;\n", encoding="utf-8")

        setup = self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.assertEqual(setup.returncode, 0)

        self.track(project_root, "src/test.ts", client_id=client_id)
        self._write_settings(project_root, timeout_hours=1)

        state_path = client_state_path(project_root, client_id)
        expired_ts = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()

        expired_review = {
            "type": "review", "reviewId": "expired-rev", "reviewPath": "p1",
            "timestamp": expired_ts, "status": "pending",
            "files": [{"file": "src/test.ts", "hash": "fake"}], "clientId": client_id,
        }
        fresh_review = {
            "type": "review", "reviewId": "fresh-rev", "reviewPath": "p2",
            "timestamp": local_now_iso(), "status": "pending",
            "files": [{"file": "src/test.ts", "hash": "fake"}], "clientId": client_id,
        }

        state_path.write_text(
            json.dumps(expired_review) + "\n" + json.dumps(fresh_review) + "\n",
            encoding="utf-8",
        )

        result = self._run_cleanup(project_root, client_id)
        self.assertEqual(result.returncode, 0)
        self.assertIn("1", result.stdout.strip())

        state_lines = [
            json.loads(line) for line in state_path.read_text(encoding="utf-8").strip().splitlines()
            if line.strip()
        ]
        review_ids = [r.get("reviewId") for r in state_lines if r.get("type") == "review"]
        self.assertNotIn("expired-rev", review_ids)
        self.assertIn("fresh-rev", review_ids)

    def test_non_expired_review_preserved(self):
        project_root = self.temp_project()
        client_id = "cleanup-fresh"
        (project_root / "src" / "app.ts").write_text("let y = 2;\n", encoding="utf-8")

        setup = self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.assertEqual(setup.returncode, 0)

        self.track(project_root, "src/app.ts", client_id=client_id)
        self._write_settings(project_root, timeout_hours=1)

        state_path = client_state_path(project_root, client_id)
        recent_ts = (datetime.now().astimezone() - timedelta(minutes=1)).isoformat()
        recent_review = {
            "type": "review", "reviewId": "recent-rev", "reviewPath": "p",
            "timestamp": recent_ts, "status": "pending",
            "files": [{"file": "src/app.ts", "hash": "fake"}], "clientId": client_id,
        }
        state_path.write_text(json.dumps(recent_review) + "\n", encoding="utf-8")

        result = self._run_cleanup(project_root, client_id)
        self.assertEqual(result.returncode, 0)
        self.assertIn("0", result.stdout.strip())

        state_lines = [
            json.loads(line) for line in state_path.read_text(encoding="utf-8").strip().splitlines()
            if line.strip()
        ]
        review_ids = [r.get("reviewId") for r in state_lines if r.get("type") == "review"]
        self.assertIn("recent-rev", review_ids)

    def test_preserves_edit_entries_and_invalid_lines(self):
        project_root = self.temp_project()
        client_id = "cleanup-mixed"

        setup = self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.assertEqual(setup.returncode, 0)

        self._write_settings(project_root, timeout_hours=1)

        state_path = client_state_path(project_root, client_id)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        expired_ts = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        entries = [
            {"type": "review", "reviewId": "exp", "reviewPath": "p",
             "timestamp": expired_ts, "status": "pending", "files": [], "clientId": client_id},
            {"type": "edit", "file": "src/lib.ts", "hash": "h",
             "timestamp": local_now_iso(), "reviewed": False},
            "invalid json line",
        ]
        state_path.write_text(
            "\n".join(
                e if isinstance(e, str) else json.dumps(e) for e in entries
            ) + "\n",
            encoding="utf-8",
        )

        result = self._run_cleanup(project_root, client_id)
        self.assertEqual(result.returncode, 0)

        content = state_path.read_text(encoding="utf-8")
        self.assertNotIn("exp", content)
        self.assertIn("edit", content)
        self.assertIn("invalid json line", content)

    def test_cleanup_logs_event(self):
        project_root = self.temp_project()
        client_id = "cleanup-log"

        setup = self.run_python("claude_auto_review/install/setup_cli.py", project_root)
        self.assertEqual(setup.returncode, 0)

        self._write_settings(project_root, timeout_hours=1)

        state_path = client_state_path(project_root, client_id)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        expired_ts = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        expired_review = {
            "type": "review", "reviewId": "log-exp", "reviewPath": "p",
            "timestamp": expired_ts, "status": "pending", "files": [], "clientId": client_id,
        }
        state_path.write_text(json.dumps(expired_review) + "\n", encoding="utf-8")

        result = self._run_cleanup(project_root, client_id)
        self.assertEqual(result.returncode, 0)

        log_path = get_log_path(project_root)
        self.assertTrue(log_path.exists())
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn("expired_reviews_cleaned", log_content)
