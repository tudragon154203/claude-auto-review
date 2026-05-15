from pathlib import Path
import sys


def ensure_repo_root_on_path():
    repo_root = Path(__file__).resolve().parents[2]
    repo_root_str = str(repo_root)
    while repo_root_str in sys.path:
        sys.path.remove(repo_root_str)
    sys.path.insert(0, repo_root_str)
