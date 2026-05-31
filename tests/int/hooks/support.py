import tempfile
from pathlib import Path

from tests.support_mixins import SubprocessMixin, TempProjectMixin
from tests.support_paths import client_dir


class HookTestCase(TempProjectMixin, SubprocessMixin):
    """Shared base for hook integration tests."""

    def temp_project(self):
        temp_dir = tempfile.TemporaryDirectory(prefix="claude-auto-review-hooks-")
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name)
        (project_root / "src").mkdir(parents=True)
        return project_root

    def complete_latest_review(
        self,
        project_root,
        verdict="Clean - no issues found. Claude may stop.",
        client_id="test-session",
    ):
        review_path = sorted((client_dir(project_root, client_id) / "reviews").glob("review-*.md"))[-1]
        content = review_path.read_text(encoding="utf-8")
        content = content.replace("Pending. Claude must complete this review from", "Completed review from")
        content = content.replace("Pending.", verdict)
        review_path.write_text(content, encoding="utf-8", newline="\n")
        return review_path
