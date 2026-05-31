import json
import tempfile
import unittest
from pathlib import Path

from tests.support_classifier_server import start_classifier_server
from tests.support_mixins import SubprocessMixin, TempProjectMixin


class EndToEndTestCase(TempProjectMixin, SubprocessMixin, unittest.TestCase):
    def temp_project(self):
        temp_dir = tempfile.TemporaryDirectory(prefix="claude-auto-review-e2e-")
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name)
        (project_root / "src").mkdir(parents=True)
        return project_root

    def track(self, project_root, file_path, client_id="test-session"):
        return self.run_python(
            "hooks/post_tool_use.py",
            project_root,
            json.dumps({"tool_input": {"file_path": file_path}}),
            client_id=client_id,
        )

    def stop(
        self,
        project_root,
        client_id="test-session",
        use_fake_claude=None,
        use_fake_codex=False,
        use_fake_opencode=False,
        env_overrides=None,
    ):
        return self.run_python(
            "hooks/stop_hook.py",
            project_root,
            client_id=client_id,
            use_fake_claude=use_fake_claude,
            use_fake_codex=use_fake_codex,
            use_fake_opencode=use_fake_opencode,
            env_overrides=env_overrides,
        )

    def review(self, project_root, client_id="test-session"):
        return self.run_python("claude_auto_review/review/prompt.py", project_root, client_id=client_id)

    def runtime_script(self, project_root, script_name):
        return project_root / ".claude" / "claude-auto-review" / "scripts" / script_name

    def read_log_entries(self, project_root):
        from claude_auto_review.runtime.client_dirs import client_state_path

        log_path = client_state_path(project_root, "test-session")
        return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def start_classifier_server(self, label="complete", payload=None):
        return start_classifier_server(label, response_payload=payload)

    def complete_review(self, project_root, verdict="Clean - no issues found.", client_id="test-session"):
        from claude_auto_review.runtime.client_dirs import client_reviews_dir

        review_dir = client_reviews_dir(project_root, client_id)
        review_path = sorted(review_dir.glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        content = content.replace(
            "Pending. Claude must complete this review from",
            "Completed review from",
        )
        content = content.replace("Pending.", verdict)
        review_path.write_text(content, encoding="utf-8", newline="\n")
        return review_path
