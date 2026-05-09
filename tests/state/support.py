import tempfile
from pathlib import Path


class StateTestCase:
    """Shared base for state unit tests providing a temp project directory."""

    def temp_project(self, prefix="claude-auto-review-"):
        return Path(tempfile.mkdtemp(prefix=prefix))
