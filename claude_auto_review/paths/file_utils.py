from pathlib import Path


def write_text_if_changed(path, content):
    path = Path(path)
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8", newline="\n")
