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
