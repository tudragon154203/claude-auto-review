#!/bin/sh
# Validates every Mermaid ```mermaid``` block in README.md renders without errors.
# Used by the git pre-commit hook (only when README.md is staged).

set -e

if ! command -v mmdc >/dev/null 2>&1; then
    echo "check-mermaid: WARNING - mermaid-cli (mmdc) not installed, skipping diagram validation"
    echo "check-mermaid: install with: npm install -g @mermaid-js/mermaid-cli"
    exit 0
fi

readme="${1:-README.md}"
if [ ! -f "$readme" ]; then
    echo "check-mermaid: $readme not found, skipping"
    exit 0
fi

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

awk -v tmpdir="$tmpdir" '
    /^```mermaid[[:space:]]*$/ { flag=1; n++; out=tmpdir "/diag_" n ".mmd"; next }
    /^```[[:space:]]*$/ { if (flag) { flag=0; close(out) } }
    flag { print > out }
' "$readme"

count=$(ls "$tmpdir"/diag_*.mmd 2>/dev/null | wc -l | tr -d ' ')
if [ "$count" = "0" ]; then
    echo "check-mermaid: no mermaid blocks found in $readme"
    exit 0
fi

echo "check-mermaid: validating $count mermaid diagram(s) in $readme"

errors=0
for f in "$tmpdir"/diag_*.mmd; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    if mmdc -i "$f" -o "${f%.mmd}.svg" >"$tmpdir/mmdc.out" 2>&1; then
        printf '  ok   %s\n' "$name"
    else
        printf '  FAIL %s\n' "$name"
        sed 's/^/        /' "$tmpdir/mmdc.out"
        errors=$((errors + 1))
    fi
done

if [ "$errors" -gt 0 ]; then
    echo "check-mermaid: $errors diagram(s) failed to render"
    exit 1
fi

echo "check-mermaid: all diagrams rendered successfully"
