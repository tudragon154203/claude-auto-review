from pathlib import Path


def build_runpy_shim_content(target_script_path):
    target_script_path = Path(target_script_path).resolve()
    script_dir = target_script_path.parent
    return (
        "#!/usr/bin/env python3\n"
        "import runpy\n"
        "import sys\n"
        f"sys.path.insert(0, {str(script_dir)!r})\n"
        f"runpy.run_path({str(target_script_path)!r}, run_name='__main__')\n"
    )


def write_project_script_shim(shim_path, plugin_script_path):
    shim_path = Path(shim_path)
    plugin_script_path = Path(plugin_script_path).resolve()
    if shim_path.resolve() == plugin_script_path:
        return
    shim_path.parent.mkdir(parents=True, exist_ok=True)
    content = build_runpy_shim_content(plugin_script_path)
    if not shim_path.exists() or shim_path.read_text(encoding="utf-8") != content:
        shim_path.write_text(content, encoding="utf-8", newline="\n")
