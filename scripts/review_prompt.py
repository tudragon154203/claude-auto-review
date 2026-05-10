#!/usr/bin/env python3
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
from scripts.review_generation import (
    build_prompt,
    current_file_snapshots,
    format_review_timestamp,
    git_diff,
    read_if_exists,
)
from scripts.shims import write_project_script_shim
from scripts.state import (
    append_review_started,
    ensure_client_runtime,
    get_unreviewed_files,
    log_event,
    load_settings,
    load_state,
)


def main():
    try:
        project_root = get_project_root()
        client_id = get_client_id()
        ensure_client_runtime(project_root, client_id)
        write_project_script_shim(
            Path(project_root) / ".claude" / "claude-auto-review" / "scripts" / "review_prompt.py",
            Path(__file__).resolve(),
        )

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
