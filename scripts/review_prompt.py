#!/usr/bin/env python3
import subprocess
from pathlib import Path

from state import (
    ensure_runtime,
    get_project_root,
    get_unreviewed_files,
    load_settings,
    load_state,
    mark_files_reviewed,
    utc_now_iso,
)


def git_diff(files, project_root):
    try:
        result = subprocess.run(
            ["git", "diff", "--", *files],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout
    except Exception as error:
        stderr = getattr(error, "stderr", "") or ""
        return f"Git diff unavailable. Review the current file contents directly.\n{stderr.strip()}"


def read_if_exists(path, fallback=""):
    path = Path(path)
    return path.read_text(encoding="utf-8") if path.exists() else fallback


def current_file_snapshots(files, project_root):
    sections = []
    max_chars = 40000
    for file_path in files:
        full_path = Path(project_root) / file_path
        if not full_path.is_file():
            sections.append(f"## {file_path}\n\nFile does not currently exist.")
            continue
        content = full_path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars:
            content = f"{content[:max_chars]}\n\n[truncated at {max_chars} characters]"
        sections.append(f"## {file_path}\n\n```\n{content}\n```")
    return "\n\n".join(sections)


def write_project_script_shim(project_root, plugin_script_path):
    runtime_scripts = Path(project_root) / ".claude" / "claude-auto-review" / "scripts"
    runtime_scripts.mkdir(parents=True, exist_ok=True)
    shim_path = runtime_scripts / "review_prompt.py"
    plugin_script_path = Path(plugin_script_path).resolve()
    content = (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "import runpy\n"
        f"sys.path.insert(0, {str(plugin_script_path.parent)!r})\n"
        f"runpy.run_path({str(plugin_script_path)!r}, run_name='__main__')\n"
    )
    if not shim_path.exists() or shim_path.read_text(encoding="utf-8") != content:
        shim_path.write_text(content, encoding="utf-8", newline="\n")


def build_prompt(review_id, timestamp, entries, rules, diff, snapshots, review_path):
    file_list = "\n".join(f"- {entry['file']} (hash: {entry['hash']})" for entry in entries)
    return f"""# Claude Auto Review Request {review_id}

You must review the changed files before stopping. Use the reviewer agent behavior from `agents/reviewer.md`: focus on semantic bugs, security, maintainability, and project rules. Do not nitpick formatting.

## Review Output

Write the final review to:

`{review_path}`

Use this exact top matter:

```markdown
# Review {review_id} - {timestamp}

## Files Reviewed
{file_list}

## Findings
```

If no findings exist, write "Clean - no issues found. Claude may stop." under "## Verdict".

## Files To Review
{file_list}

## Rules
{rules}

## Git Diff
```diff
{diff}
```

## Current File Snapshots
{snapshots}

## After Review

Fix any CRITICAL or HIGH findings you agree with. If you edit files, the hook will track those new hashes and require another review pass."""


def main():
    try:
        project_root = get_project_root()
        runtime = ensure_runtime(project_root)
        write_project_script_shim(project_root, Path(__file__).resolve())

        settings = load_settings(project_root)
        if not settings.get("enabled", True):
            print("Claude Auto Review is disabled in .claude/settings.json.")
            return 0

        unreviewed = get_unreviewed_files(load_state(project_root))
        if not unreviewed:
            print("Claude Auto Review: no unreviewed changes.")
            return 0

        timestamp = utc_now_iso()
        review_id = "rev-" + "".join(ch for ch in timestamp if ch.isdigit())[:14]
        files = [entry["file"] for entry in unreviewed]
        configured_rules = settings.get("rulesFile") or runtime["rules_path"]
        rules_path = Path(configured_rules)
        if not rules_path.is_absolute():
            rules_path = Path(project_root) / rules_path
        rules = read_if_exists(rules_path, read_if_exists(runtime["rules_path"]))
        diff = git_diff(files, project_root)
        snapshots = current_file_snapshots(files, project_root)

        review_path = runtime["reviews_dir"] / f"review-{review_id}.md"
        prompt_path = runtime["run_dir"] / f"review-{review_id}-prompt.md"
        prompt_path.write_text(
            build_prompt(review_id, timestamp, unreviewed, rules, diff, snapshots, review_path),
            encoding="utf-8",
            newline="\n",
        )
        file_list = "\n".join(f"- {entry['file']} (hash: {entry['hash']})" for entry in unreviewed)
        review_path.write_text(
            f"""# Review {review_id} - {timestamp}

## Files Reviewed
{file_list}

## Findings

Pending. Claude must complete this review from {prompt_path}.

## Verdict

Pending.
""",
            encoding="utf-8",
            newline="\n",
        )

        mark_files_reviewed(unreviewed, review_id, project_root)
        print(f"Claude Auto Review prompt created: {prompt_path}")
        print(f"Review file initialized: {review_path}")
        print("Read the prompt, complete the review file, and fix any agreed CRITICAL or HIGH findings before stopping.")
        return 0
    except Exception as error:
        print(f"Claude Auto Review failed open: {error}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
