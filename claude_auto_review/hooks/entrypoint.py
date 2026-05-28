from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType


def repo_root_from_file(file_path: str) -> Path:
    return Path(file_path).resolve().parent.parent


def ensure_repo_root_on_path(file_path: str) -> Path:
    repo_root = repo_root_from_file(file_path)
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    return repo_root


def run_module_main(module_name: str) -> int:
    module: ModuleType = import_module(module_name)
    return int(module.main())
