#!/usr/bin/env python3
import subprocess
from datetime import datetime
from pathlib import Path

from bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.paths import (
    client_reviews_dir,
    client_run_dir,
    get_client_id,
    get_project_root,
    utc_now_iso,
)
from scripts.shims import build_runpy_shim_content
from scripts.state import (
    append_review_started,
    ensure_client_runtime,
    ensure_runtime,
    get_unreviewed_files,
    log_event,
    load_settings,
    load_state,
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


def format_review_timestamp(timestamp):
    ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    local_ts = ts.astimezone()
    offset = local_ts.strftime("%z")
    offset = f"{offset[:3]}:{offset[3:]}" if offset else ""
    return f"{local_ts.strftime('%Y-%m-%d | %H:%M:%S')} {offset}".rstrip()


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
    content = build_runpy_shim_content(plugin_script_path)
    if not shim_path.exists() or shim_path.read_text(encoding="utf-8") != content:
        shim_path.write_text(content, encoding="utf-8", newline="\n")


def build_prompt(review_id, timestamp, entries, rules, diff, snapshots, review_path):
    readable_timestamp = format_review_timestamp(timestamp)
    file_list = "\n".join(f"- {entry['file']} (hash: {entry['hash']})" for entry in entries)
    return f"""# Claude Auto Review Request {review_id}

You must review the changed files before stopping. Use the reviewer agent behavior from `agents/reviewer.md`: focus on semantic bugs, security, maintainability, and project rules. Do not nitpick formatting.

## Review Output

Write the final review to:

`{review_path}`

Use this exact top matter:

```markdown
# Review {review_id} - {readable_timestamp}

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

After receiving review results:

1. Show all findings to the user.
2. Evaluate each finding against one heuristic: what produces the highest quality code?
3. Fix the finding unless one of these skip reasons clearly applies:
   - IMPOSSIBLE: you tried the fix and cannot satisfy feedback, product requirements, lint rules, and tests simultaneously.
   - CONFLICTS WITH REQUIREMENTS: the feedback directly contradicts explicit product requirements.
   - MAKES CODE WORSE: applying the feedback would genuinely degrade code quality.
4. These are not valid skip reasons:
   - too much time
   - too complex
   - out of scope after you touched the file
   - pre-existing code
   - only renamed or moved
   - would require a larger refactor
5. If uncertain, ask the user.

If you edit files, the hook will track those new hashes and require another review pass."""


def main():
    try:
        project_root = get_project_root()
        client_id = get_client_id()
        ensure_client_runtime(project_root, client_id)
        write_project_script_shim(project_root, Path(__file__).resolve())

        settings = load_settings(project_root)
        if not settings.get("enabled", True):
            log_event(project_root, "review_prompt_disabled")
            print("Claude Auto Review is disabled in .claude/settings.json.")
            return 0

        unreviewed = get_unreviewed_files(load_state(project_root, client_id))
        if not unreviewed:
            log_event(project_root, "review_prompt_noop")
            print("Claude Auto Review: no unreviewed changes.")
            return 0

        timestamp = utc_now_iso()
        review_id = "rev-" + "".join(ch for ch in timestamp if ch.isdigit())[:14]
        files = [entry["file"] for entry in unreviewed]

        # Determine rules path
        rules_path = Path(settings.get("rulesFile", ""))
        if not rules_path.is_absolute():
            rules_path = project_root / ".claude" / "claude-auto-review" / "rules.md"
        rules = read_if_exists(rules_path)

        diff = git_diff(files, project_root)
        snapshots = current_file_snapshots(files, project_root)

        review_path = client_reviews_dir(project_root, client_id) / f"review-{review_id}.md"
        prompt_path = client_run_dir(project_root, client_id) / f"review-{review_id}-prompt.md"
        prompt_path.write_text(
            build_prompt(review_id, timestamp, unreviewed, rules, diff, snapshots, review_path),
            encoding="utf-8",
            newline="\n",
        )
        file_list = "\n".join(f"- {entry['file']} (hash: {entry['hash']})" for entry in unreviewed)
        review_path.write_text(
            f"""# Review {review_id} - {format_review_timestamp(timestamp)}

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

        append_review_started(unreviewed, review_id, review_path, project_root, client_id=client_id)
        log_event(
            project_root,
            "review_prompt_created",
            reviewId=review_id,
            files=files,
            prompt=str(prompt_path),
            review=str(review_path),
            clientId=client_id,
        )
        print(f"Claude Auto Review prompt created: {prompt_path}")
        print(f"Review file initialized: {review_path}")
        print("Read the prompt, complete the review file, and fix any agreed CRITICAL or HIGH findings before stopping.")
        return 0
    except Exception as error:
        try:
            log_event(get_project_root(), "review_prompt_error", error=str(error))
        except Exception:
            pass
        print(f"Claude Auto Review failed open: {error}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
