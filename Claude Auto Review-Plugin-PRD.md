# PRD: Claude Auto Review — Claude Code Plugin

**Version:** 1.0.0-draft  
**Date:** 2026-05-05  
**Status:** Design Phase  
**Author:** User + Claude  

---

## 1. Executive Summary

Claude Auto Review is a Claude Code plugin that automatically reviews code immediately after Claude finishes writing it, then keeps Claude alive to fix issues it agrees with. It merges the best of two existing plugins:

- 1. **`hamelsmu/claude-review-loop`** — Stop-hook blocking pattern, 4 Codex agents
     
     - [GitHub - hamelsmu/claude-review-loop: Claude Code plugin: automated code review loop with Codex · GitHub](https://github.com/hamelsmu/claude-review-loop)
  
  2. **`NTCoding/claude-skillz`** (`automatic-code-review` plugin) — File tracking, semantic rules, subagent review
     
     - [GitHub - NTCoding/claude-skillz: Random Claude skills for common, simple programming tasks · GitHub](https://github.com/NTCoding/claude-skillz)
     
     - Specific plugin directory: [claude-skillz/automatic-code-review at main · NTCoding/claude-skillz · GitHub](https://github.com/NTCoding/claude-skillz/tree/main/automatic-code-review)

The result: a **single-agent, diff-focused, rules-driven review loop** that is fast, cheap, and catches semantic issues linters miss.

---

## 2. Problem Statement

### 2.1 Current Pain Points

| Problem                                               | Existing Solutions        | Why They Fail                                                            |
| ----------------------------------------------------- | ------------------------- | ------------------------------------------------------------------------ |
| Claude writes code, user must manually ask for review | None (default behavior)   | Easy to forget; bugs slip through                                        |
| Review loops are redundant                            | `claude-review-loop`      | Always runs 4 Codex agents, even for trivial changes; no change tracking |
| Reviews lack project context                          | `automatic-code-review`   | Review-only, no auto-fix; generic rules                                  |
| Hook scripts are fragile                              | Various community plugins | Bash-only, no Windows support; hard to debug                             |

### 2.2 User Needs

1. **Zero-friction**: Review happens automatically when Claude finishes editing — no slash commands to remember.
2. **Smart skipping**: Don't re-review files that haven't changed since the last review.
3. **Semantic depth**: Catch issues like bad naming, domain logic leakage, dangerous fallbacks — not just syntax.
4. **Auto-fix loop**: Claude reads the review and fixes what it agrees with, then stops only when clean.
5. **Cross-platform**: Works on Windows, macOS, Linux without WSL or Git Bash dependencies.
6. **Project-specific rules**: Each repo defines its own review criteria, committed to git.

---

## 3. Design Principles

| Principle                     | Rationale                                                                                                                         |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **One agent, one job**        | A single reviewer with a rich rules file beats 4 parallel generalists. Lower cost, simpler orchestration, smaller context window. |
| **Diff-only, not holistic**   | Review what changed (`git diff`), not the entire codebase. Faster, more relevant, less token waste.                               |
| **State is explicit**         | Track reviewed file hashes in a local state file. No hidden magic, no redundant reviews.                                          |
| **Fail open, not closed**     | If hooks error, allow Claude to proceed. Never block the user because a plugin broke.                                             |
| **Rules are code**            | Review criteria live in `.claude/claude-auto-review/rules.md`, committed to git, version-controlled, team-shared.                               |
| **Cross-platform by default** | All hook scripts in Node.js (or Python), not bash. Single codebase, all platforms.                                                |

---

## 4. Architecture

### 4.1 High-Level Flow

```
User: "Add user authentication"
  │
  ▼
Claude writes/edits files
  │
  ▼
PostToolUse Hook ─────────────────────────────────────────────┐
  │                                                          │
  ▼                                                          │
Log file path + content hash to `.claude/claude-auto-review/state.jsonl`   │
  │                                                          │
  ▼                                                          │
Claude finishes task → Stop Hook fires                       │
  │                                                          │
  ▼                                                          │
Read state.jsonl → compare hashes with last review          │
  │                                                          │
  ├─ No new changes ──→ Allow stop (exit 0)                │
  │                                                          │
  └─ New changes found ──→ BLOCK stop (exit 2)              │
         │                                                   │
         ▼                                                   │
    Write review prompt + file list to `.claude/claude-auto-review/run/`   │
         │                                                   │
         ▼                                                   │
    Claude reads prompt → runs review subagent             │
         │                                                   │
         ▼                                                   │
    Subagent reads rules.md + git diff → writes review      │
         │                                                   │
         ▼                                                   │
    Review written to `.claude/claude-auto-review/reviews/review-{id}.md` │
         │                                                   │
         ▼                                                   │
    Claude reads review → fixes agreed items                │
         │                                                   │
         ▼                                                   │
    Loop: PostToolUse logs new changes ──→ Stop checks again │
         │                                                   │
         └─ Clean? ──→ Allow stop (exit 0) ◄─────────────────┘
```

### 4.2 Component Diagram

```
claude-auto-review/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
│
├── commands/
│   └── claude-auto-review.md                  # /claude-auto-review — manual trigger (optional)
│
├── hooks/
│   ├── hooks.json               # Hook registrations (PostToolUse, Stop)
│   ├── post-tool-use.js         # Cross-platform file change logger
│   └── stop-hook.js             # Change detector + stop blocker + review orchestrator
│
├── scripts/
│   ├── review-prompt.js         # Generates review prompt from state + rules
│   └── setup-claude-auto-review.js            # First-run initialization (rules.md, state file)
│
├── agents/
│   └── reviewer.md              # Single-agent system prompt for the reviewer
│
├── rules/
│   └── default-rules.md         # Default semantic rules (shipped with plugin)
│
└── AGENTS.md                    # Plugin documentation for Claude
```

### 4.3 State Management

**File:** `.claude/claude-auto-review/state.jsonl` (gitignored)

```jsonl
{"type":"edit","file":"src/auth.ts","hash":"a3f7b2","timestamp":"2026-05-05T11:30:00Z","reviewed":false}
{"type":"edit","file":"src/auth.ts","hash":"a3f7b2","timestamp":"2026-05-05T11:35:00Z","reviewed":true,"reviewId":"rev-001"}
{"type":"edit","file":"src/login.tsx","hash":"c8d1e4","timestamp":"2026-05-05T11:36:00Z","reviewed":false}
```

**Schema:**
| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `edit` or `review` |
| `file` | string | Relative path from git root |
| `hash` | string | SHA-256 of file content (first 8 chars) |
| `timestamp` | ISO 8601 | When the event occurred |
| `reviewed` | boolean | Whether this hash has been reviewed |
| `reviewId` | string? | ID of the review that covered this file |

**Review output:** `.claude/claude-auto-review/reviews/review-{id}.md`

```markdown
# Review rev-002 — 2026-05-05T11:40:00Z

## Files Reviewed
- src/auth.ts (hash: a3f7b2)
- src/login.tsx (hash: c8d1e4)

## Findings

### [MEDIUM] Naming: `handleLogin` → `authenticateUser`
- **Location:** src/auth.ts:42
- **Rule:** "Use domain verbs, not generic handlers"
- **Rationale:** `handleLogin` leaks HTTP concern into domain layer

### [HIGH] Dangerous fallback
- **Location:** src/auth.ts:58
- **Rule:** "Never use default fallbacks for auth decisions"
- **Rationale:** `role ?? 'user'` grants user privileges if role is missing

## Verdict
2 issues found. Claude should address [HIGH] before stopping.
```

---

## 5. Hook Design

### 5.1 PostToolUse Hook

**Event:** After every `Write`, `Edit`, or `MultiEdit` tool call.

**Behavior:**

1. Extract `file_path` from tool input.
2. Compute SHA-256 hash of file content.
3. Append entry to `state.jsonl` with `reviewed: false`.
4. If file was previously reviewed with same hash, mark `reviewed: true` immediately (no-op edit).

**Timeout:** 2 seconds (fast, non-blocking).

**Exit code:** Always 0 (never block edits).

**Implementation:** `hooks/post-tool-use.js`

```javascript
#!/usr/bin/env node
// hooks/post-tool-use.js
const fs = require('fs');
const crypto = require('crypto');
const path = require('path');

const STATE_FILE = '.claude/claude-auto-review/state.jsonl';
const GIT_ROOT = process.env.CLAUDE_PROJECT_DIR || process.cwd();

function getFileHash(filePath) {
  const fullPath = path.join(GIT_ROOT, filePath);
  if (!fs.existsSync(fullPath)) return null;
  const content = fs.readFileSync(fullPath);
  return crypto.createHash('sha256').update(content).digest('hex').slice(0, 8);
}

function appendState(entry) {
  const statePath = path.join(GIT_ROOT, STATE_FILE);
  const dir = path.dirname(statePath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.appendFileSync(statePath, JSON.stringify(entry) + '\n');
}

// Read tool input from stdin (Claude Code hook protocol)
let toolInput = '';
process.stdin.on('data', chunk => toolInput += chunk);
process.stdin.on('end', () => {
  try {
    const input = JSON.parse(toolInput);
    const filePath = input.file_path || input.path;
    if (!filePath) process.exit(0);

    const hash = getFileHash(filePath);
    if (!hash) process.exit(0);

    appendState({
      type: 'edit',
      file: filePath,
      hash,
      timestamp: new Date().toISOString(),
      reviewed: false
    });

    process.exit(0);
  } catch (e) {
    // Fail open: never block on hook error
    process.exit(0);
  }
});
```

### 5.2 Stop Hook

**Event:** When Claude attempts to finish the session.

**Behavior:**

1. Read `state.jsonl`.
2. Group entries by file, keep only latest hash per file.
3. Check if any file has `reviewed: false` (new changes since last review).
4. If **no new changes** → allow stop (exit 0).
5. If **new changes found** → block stop (exit 2) with message instructing Claude to run review.

**Message format:**

```json
{
  "block": true,
  "message": "Claude Auto Review: Unreviewed changes detected in src/auth.ts, src/login.tsx. Running review...",
  "feedback": "Review required before stopping. Run the review script: node .claude/claude-auto-review/scripts/review-prompt.js"
}
```

**Timeout:** 5 seconds.

**Implementation:** `hooks/stop-hook.js`

```javascript
#!/usr/bin/env node
// hooks/stop-hook.js
const fs = require('fs');
const path = require('path');

const STATE_FILE = '.claude/claude-auto-review/state.jsonl';
const GIT_ROOT = process.env.CLAUDE_PROJECT_DIR || process.cwd();

function loadState() {
  const statePath = path.join(GIT_ROOT, STATE_FILE);
  if (!fs.existsSync(statePath)) return [];
  return fs.readFileSync(statePath, 'utf8')
    .trim()
    .split('\n')
    .filter(Boolean)
    .map(line => JSON.parse(line));
}

function getUnreviewedFiles(state) {
  const latestByFile = {};
  for (const entry of state) {
    if (!latestByFile[entry.file] || new Date(entry.timestamp) > new Date(latestByFile[entry.file].timestamp)) {
      latestByFile[entry.file] = entry;
    }
  }
  return Object.values(latestByFile).filter(e => !e.reviewed);
}

function main() {
  try {
    const state = loadState();
    const unreviewed = getUnreviewedFiles(state);

    if (unreviewed.length === 0) {
      // All clean, allow stop
      process.exit(0);
    }

    const files = unreviewed.map(e => e.file).join(', ');
    const reviewScript = path.join(GIT_ROOT, '.claude/claude-auto-review/scripts/review-prompt.js');

    // Block stop and tell Claude what to do
    const response = {
      block: true,
      message: `Claude Auto Review: Unreviewed changes in ${files}. Running review...`,
      feedback: `Run: node ${reviewScript}`,
      continue: false
    };

    console.log(JSON.stringify(response));
    process.exit(2); // Blocking error
  } catch (e) {
    // Fail open
    process.exit(0);
  }
}

main();
```

### 5.3 Review Orchestration Script

**File:** `scripts/review-prompt.js`

**Behavior:**

1. Read unreviewed files from state.
2. Read `.claude/claude-auto-review/rules.md` (or fallback to default).
3. Run `git diff` for unreviewed files.
4. Generate a prompt file for the reviewer agent.
5. Execute the review via Claude Code's Bash tool (or spawn subagent if supported).
6. Write review output to `.claude/claude-auto-review/reviews/review-{id}.md`.
7. Mark files as `reviewed: true` in state.

**Subagent invocation (Claude Code native):**

```bash
claude -p "Review these files: src/auth.ts, src/login.tsx. Rules: .claude/claude-auto-review/rules.md. Diff: $(git diff -- src/auth.ts src/login.tsx)" --agent .claude/claude-auto-review/agents/reviewer.md
```

---

## 6. Rules System

### 6.1 Rules File Location

**Primary:** `.claude/claude-auto-review/rules.md` (project-specific, committed to git)  
**Fallback:** Plugin's `rules/default-rules.md` (shipped with plugin)

### 6.2 Rules Format

```markdown
# Claude Auto Review Rules

## Naming
- Use domain verbs, not generic handlers (`authenticateUser`, not `handleLogin`)
- No `helper`, `utils`, `manager` suffixes without domain context
- Boolean variables start with `is`, `has`, `should`

## Type Safety
- No `any` — use `unknown` with type guards
- No bare string primitives for IDs/emails — use branded types
- Validate all external inputs at system boundary

## Domain Logic
- Business rules belong in domain layer, not controllers
- No conditional logic in API route handlers
- Use exhaustive switch/case, no implicit fallthrough

## Security
- Never use default fallbacks for auth decisions
- Sanitize all user input before DB queries
- No secrets in logs or error messages

## Error Handling
- Fail fast with specific errors
- No silent catches — log or propagate
- Async errors must be awaited or handled
```

### 6.3 Rule Severity Levels

| Level        | Action Required         | Examples                                    |
| ------------ | ----------------------- | ------------------------------------------- |
| **CRITICAL** | Block stop until fixed  | Security vulnerabilities, data loss risk    |
| **HIGH**     | Strongly recommended    | Type safety violations, dangerous fallbacks |
| **MEDIUM**   | Address if time permits | Naming issues, minor logic leakage          |
| **LOW**      | Informational           | Style preferences, optional improvements    |

---

## 7. Agent Design

### 7.1 Single Reviewer Agent

**File:** `agents/reviewer.md`

```markdown
---
name: claude-auto-review-reviewer
description: Reviews code changes for semantic quality, security, and project conventions. Triggered automatically after file edits.
model: sonnet
tools: ["Read", "Grep", "Bash", "Glob"]
---

# Claude Auto Review Reviewer

You are a senior engineer doing code review. You are skeptical, thorough, and focused on issues a linter cannot catch.

## Your Process
1. Read `.claude/claude-auto-review/rules.md` (project rules)
2. Run `git diff` for the files listed in the review request
3. Read the current file content if needed for context
4. Apply each rule from rules.md to the diff
5. Write findings to `.claude/claude-auto-review/reviews/review-{id}.md`

## Output Format
For each finding:
- **Severity:** CRITICAL / HIGH / MEDIUM / LOW
- **Rule:** Which rule was violated (quote it)
- **Location:** File and line number
- **Rationale:** Why this matters (1-2 sentences)
- **Suggestion:** Concrete fix (code snippet if helpful)

## Verdict
End with one of:
- "Clean — no issues found. Claude may stop."
- "N issues found. Claude should address [CRITICAL/HIGH] items before stopping."
- "N issues found. All are [MEDIUM/LOW]. Claude may stop and address later."

## Constraints
- Do NOT review files not in the diff
- Do NOT suggest formatting issues (handled by Prettier/lint)
- Do NOT nitpick variable names unless they violate rules
- Focus on semantics, not syntax
```

---

## 8. Installation

### 8.1 Prerequisites

- Claude Code CLI v2.1.0+
- Node.js 18+ (for cross-platform hook scripts)
- Git (for `git diff`)

### 8.2 Plugin Install

```bash
# Add marketplace
/plugin marketplace add <your-org>/claude-auto-review

# Install plugin
/plugin install claude-auto-review@<your-org>
```

### 8.3 First-Run Setup

The plugin auto-initializes on first `PostToolUse` hook:

1. Creates `.claude/claude-auto-review/` directory
2. Copies `rules/default-rules.md` → `.claude/claude-auto-review/rules.md` (if no existing rules)
3. Creates empty `state.jsonl`
4. Creates `reviews/` directory

### 8.4 Manual Setup (Optional)

```bash
# Clone repo
git clone https://github.com/<your-org>/claude-auto-review.git
cd claude-auto-review

# Install hooks manually (if not using plugin system)
node scripts/setup-claude-auto-review.js
```

---

## 9. Configuration

### 9.1 Plugin Manifest

**File:** `.claude-plugin/plugin.json`

```json
{
  "name": "claude-auto-review",
  "version": "1.0.0",
  "description": "Post-Edit Review Loop — automatic code review after Claude writes code",
  "author": "<your-org>",
  "license": "MIT",
  "commands": ["claude-auto-review"],
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit|MultiEdit",
      "script": "hooks/post-tool-use.js",
      "timeout": 2
    }],
    "Stop": [{
      "script": "hooks/stop-hook.js",
      "timeout": 5
    }]
  },
  "agents": ["agents/reviewer.md"],
  "rules": ["rules/default-rules.md"]
}
```

### 9.2 User Settings

**File:** `.claude/settings.json` (project-level overrides)

```json
{
  "claude-auto-review": {
    "enabled": true,
    "rulesFile": ".claude/claude-auto-review/rules.md",
    "skipExtensions": ["md", "json", "yaml", "yml", "css", "scss"],
    "minSeverity": "MEDIUM",
    "autoFix": true
  }
}
```

| Setting          | Default                 | Description                             |
| ---------------- | ----------------------- | --------------------------------------- |
| `enabled`        | `true`                  | Master toggle                           |
| `rulesFile`      | `.claude/claude-auto-review/rules.md` | Path to project rules                   |
| `skipExtensions` | `[]`                    | File types to ignore                    |
| `minSeverity`    | `"MEDIUM"`              | Only block stop for ≥ this severity     |
| `autoFix`        | `true`                  | Claude attempts fixes for CRITICAL/HIGH |

---

## 10. Development Plan

### 10.1 Milestones

| Phase  | Deliverable                                             | ETA    |
| ------ | ------------------------------------------------------- | ------ |
| **M1** | Core hooks (PostToolUse + Stop) with file tracking      | Week 1 |
| **M2** | Reviewer agent + rules system + default rules           | Week 2 |
| **M3** | Review orchestration script + output formatting         | Week 3 |
| **M4** | Auto-fix loop integration (Claude reads review → fixes) | Week 4 |
| **M5** | Plugin packaging + marketplace publishing               | Week 5 |
| **M6** | Documentation + examples + community feedback           | Week 6 |

### 10.2 File Checklist

```
claude-auto-review/
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   └── reviewer.md
├── commands/
│   └── claude-auto-review.md
├── hooks/
│   ├── hooks.json
│   ├── post-tool-use.js
│   └── stop-hook.js
├── scripts/
│   ├── review-prompt.js
│   └── setup-claude-auto-review.js
├── rules/
│   └── default-rules.md
├── tests/
│   ├── hooks.test.js
│   ├── state.test.js
│   └── rules.test.js
├── docs/
│   ├── README.md
│   ├── INSTALL.md
│   └── RULES-GUIDE.md
├── package.json
├── justfile / Makefile
└── LICENSE
```

### 10.3 Testing Strategy

| Test Type      | Tool                                    | Coverage                                     |
| -------------- | --------------------------------------- | -------------------------------------------- |
| Unit tests     | Vitest                                  | Hook scripts, state management, rules parser |
| Integration    | Claude Code test harness                | End-to-end review loop                       |
| Cross-platform | GitHub Actions (ubuntu, macos, windows) | CI for all hooks                             |

---

## 11. Open Questions

1. **Subagent API**: Claude Code's subagent spawning is still evolving. Do we use `claude -p` CLI, native `TaskCreate`, or wait for plugin-native agent dispatch?
2. **Auto-fix scope**: Should Claude auto-fix only CRITICAL, or CRITICAL+HIGH? Should user confirm each fix?
3. **Multi-file reviews**: If 10 files changed, do we review all at once (large context) or batch (more API calls)?
4. **Cost ceiling**: Should we cap review cost per session? (e.g., max $0.50, then warn and allow stop)
5. **IDE integration**: Should reviews also post as VS Code diagnostics / GitHub PR comments?

---

## 12. References

- `hamelsmu/claude-review-loop` — Stop-hook blocking pattern, Codex multi-agent
- `NTCoding/claude-skillz` (`automatic-code-review` plugin) — File tracking, semantic rules, subagent review
- `0xDarkMatter/claude-mods` — Production plugin structure, cross-platform scripts, Agent Skills spec
- `ChrisWiles/claude-code-showcase` — Hook configuration reference, settings.json schema
- Anthropic Claude Code Plugin Docs — Hook events, response formats, exit codes

---

*End of PRD*
