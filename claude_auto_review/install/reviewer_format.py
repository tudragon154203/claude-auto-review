"""Analyze and normalize reviewer.md finding examples for parser compatibility."""
from __future__ import annotations

import re
from pathlib import Path

_FIELD_ALIASES = {
    "fix": "suggestion",
    "impact": "rationale",
    "priority": "severity",
    "category": "rule",
}

_SEVERITY_MAP = {
    "critical": "critical", "severe": "critical", "blocker": "critical",
    "high": "high", "major": "high", "important": "high", "significant": "high",
    "medium": "medium", "moderate": "medium", "med": "medium", "normal": "medium",
    "low": "low", "minor": "low", "trivial": "low",
    "info": "info", "information": "info", "informational": "info", "note": "info",
}

_VALID_SEVERITIES = {"info", "low", "medium", "high", "critical"}

_FINDING_LINE_RE = re.compile(r"^(\s*)[-*]\s*(Confirmed|Skipped)\s*:\s*(.+)$", re.MULTILINE)
_FIELD_LINE_RE = re.compile(r"^(\s+)\*{0,2}([A-Za-z]+)\*{0,2}:\s*(.+)$", re.MULTILINE)
_CHECK_RE = re.compile(r"^[-*]\s*(Confirmed|Skipped):\s*(.+)$", re.MULTILINE)
_FIELD_CHECK_RE = re.compile(r"^\s+(Severity|Verdict|Reason|Rule|Location|Rationale|Suggestion):\s*(.+)$", re.MULTILINE)


def _normalize_severity(value: str) -> tuple[str | None, bool]:
    """Return (canonical_severity, was_changed). None if unrecognized."""
    lowered = value.strip().lower()
    canonical = _SEVERITY_MAP.get(lowered)
    if canonical is None:
        lowered_clean = lowered.strip("`*").strip()
        canonical = _SEVERITY_MAP.get(lowered_clean)
    return (canonical, canonical is not None and canonical != lowered.strip())


def _normalize_field_name(raw: str) -> str:
    key = raw.strip().lower().rstrip(":")
    return _FIELD_ALIASES.get(key, key)


def _strip_leading_bold(value: str) -> tuple[str, bool]:
    stripped = value.strip()
    changed = stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2
    return (stripped.strip("*").strip(), changed)


def analyze_reviewer(text: str) -> tuple[str, list[str], bool]:
    """Normalize reviewer.md finding examples to parser-compatible format without writing to disk.

    Returns (repaired_text, warnings, was_modified).
    """
    if not text.strip():
        return text, ["reviewer.md is empty — skipping format consistency check"], False

    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    in_finding = False

    for line in lines:
        m_bullet = _FINDING_LINE_RE.match(line)
        if m_bullet:
            in_finding = True
            indent = m_bullet.group(1)
            verdict = m_bullet.group(2)
            rest, _ = _strip_leading_bold(m_bullet.group(3))
            new_lines.append(f"{indent}- {verdict}: {rest}\n")
            continue

        if in_finding:
            stripped = line.rstrip("\n\r")
            if not stripped.strip():
                in_finding = False
                new_lines.append(line)
                continue
            m_field = _FIELD_LINE_RE.match(stripped)
            if m_field:
                indent_raw = stripped[: len(stripped) - len(stripped.lstrip())]
                raw_name = m_field.group(2)
                raw_value = m_field.group(3)
                canonical = _normalize_field_name(raw_name)
                if canonical == "severity":
                    mapped, changed = _normalize_severity(raw_value)
                    value_out = mapped if mapped is not None else raw_value.strip()
                else:
                    value_out, _ = _strip_leading_bold(raw_value)
                new_lines.append(f"{indent_raw}{canonical.capitalize()}: {value_out}\n")
                continue
            if not stripped.startswith((" ", "\t")):
                in_finding = False
            new_lines.append(line)
        else:
            new_lines.append(line)

    repaired = "".join(new_lines)

    warnings: list[str] = []
    for m in _CHECK_RE.finditer(repaired):
        verdict = m.group(1).lower()
        title = m.group(2).strip()
        if title.startswith("**") or title.startswith("<") or title.startswith("title"):
            continue
        if verdict == "skipped":
            continue
        line_no = repaired[:m.start()].count("\n") + 1
        after = repaired[m.end():]
        field_lines: list[tuple[str, str]] = []
        for ln in after.splitlines():
            s = ln.rstrip()
            if not s:
                continue
            fm = _FIELD_CHECK_RE.match(s)
            if fm:
                field_lines.append((fm.group(1).lower(), fm.group(2).strip()))
            else:
                break
        sv = next((v for k, v in field_lines if k == "severity"), None)
        if sv is None:
            warnings.append(f"reviewer.md:{line_no} — Confirmed finding has no Severity field")
        elif sv.lower() not in _VALID_SEVERITIES and "|" not in sv and not sv.startswith("<"):
            warnings.append(
                f"reviewer.md:{line_no} — unrecognized Severity value '{sv}' "
                f"(expected one of: {', '.join(sorted(_VALID_SEVERITIES))})"
            )

    return repaired, warnings, repaired != text


def check_and_repair_reviewer(plugin_root: Path) -> tuple[str | None, list[str], bool]:
    """Analyze source reviewer.md and return repaired text if needed.

    Source files under plugin_root are never modified.
    Returns (repaired_text_or_None, warnings, was_repair_applied).
    """
    source_path = plugin_root / "agents" / "reviewer.md"
    if not source_path.is_file():
        return None, ["reviewer.md not found — skipping format consistency check"], False

    try:
        source_text = source_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return None, [f"reviewer.md read failed ({exc}); falling back to direct copy"], False

    repaired_text, warnings, was_modified = analyze_reviewer(source_text)

    if was_modified:
        return repaired_text, warnings, True
    return None, warnings, False
