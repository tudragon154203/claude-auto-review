from __future__ import annotations


def _build_claude_review_args(model):
    return [
        "--print",
        "--bare",
        "--allowedTools",
        "Read",
        "Grep",
        "Glob",
        "Bash",
        "--model",
        model,
        "--effort",
        "low",
    ]


def _build_codex_review_args(model):
    return [
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--model",
        model,
        "-",
    ]


def _build_opencode_review_args(model, prompt_file):
    args = [
        "run",
        "--pure",
        "Review the attached prompt file and respond with your findings.",
    ]
    if model not in ("", "default", "none"):
        args.extend(["--model", model])
    args.extend(["--file", str(prompt_file)])
    return args
