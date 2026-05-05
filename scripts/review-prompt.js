#!/usr/bin/env node
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const {
  ensureRuntime,
  getProjectRoot,
  getUnreviewedFiles,
  loadSettings,
  loadState,
  markFilesReviewed
} = require('./state');

function shellGitDiff(files, projectRoot) {
  try {
    return execFileSync('git', ['diff', '--', ...files], {
      cwd: projectRoot,
      encoding: 'utf8',
      maxBuffer: 10 * 1024 * 1024
    });
  } catch (error) {
    const stderr = error && error.stderr ? String(error.stderr).trim() : '';
    return `Git diff unavailable. Review the current file contents directly.\n${stderr}`;
  }
}

function readIfExists(filePath, fallback = '') {
  return fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : fallback;
}

function currentFileSnapshots(files, projectRoot) {
  return files.map((file) => {
    const fullPath = path.join(projectRoot, file);
    if (!fs.existsSync(fullPath) || !fs.statSync(fullPath).isFile()) {
      return `## ${file}\n\nFile does not currently exist.`;
    }
    const content = fs.readFileSync(fullPath, 'utf8');
    const maxChars = 40000;
    const truncated = content.length > maxChars
      ? `${content.slice(0, maxChars)}\n\n[truncated at ${maxChars} characters]`
      : content;
    return `## ${file}\n\n\`\`\`\n${truncated}\n\`\`\``;
  }).join('\n\n');
}

function writeProjectScriptShim(projectRoot, pluginScriptPath) {
  const runtimeScripts = path.join(projectRoot, '.claude', 'claude-auto-review', 'scripts');
  fs.mkdirSync(runtimeScripts, { recursive: true });
  const shimPath = path.join(runtimeScripts, 'review-prompt.js');
  const relative = path.relative(runtimeScripts, pluginScriptPath).split(path.sep).join('/');
  const content = `#!/usr/bin/env node\nrequire(${JSON.stringify(relative)});\n`;
  if (!fs.existsSync(shimPath) || fs.readFileSync(shimPath, 'utf8') !== content) {
    fs.writeFileSync(shimPath, content);
  }
}

function buildPrompt({ reviewId, timestamp, files, rules, diff, snapshots, reviewPath }) {
  const fileList = files.map((entry) => `- ${entry.file} (hash: ${entry.hash})`).join('\n');
  return `# Claude Auto Review Request ${reviewId}

You must review the changed files before stopping. Use the reviewer agent behavior from \`agents/reviewer.md\`: focus on semantic bugs, security, maintainability, and project rules. Do not nitpick formatting.

## Review Output

Write the final review to:

\`${reviewPath}\`

Use this exact top matter:

\`\`\`markdown
# Review ${reviewId} - ${timestamp}

## Files Reviewed
${fileList}

## Findings
\`\`\`

If no findings exist, write "Clean - no issues found. Claude may stop." under "## Verdict".

## Files To Review
${fileList}

## Rules
${rules}

## Git Diff
\`\`\`diff
${diff}
\`\`\`

## Current File Snapshots
${snapshots}

## After Review

Fix any CRITICAL or HIGH findings you agree with. If you edit files, the hook will track those new hashes and require another review pass.`;
}

function main() {
  try {
    const projectRoot = getProjectRoot();
    const runtime = ensureRuntime(projectRoot);
    writeProjectScriptShim(projectRoot, __filename);

    const settings = loadSettings(projectRoot);
    if (!settings.enabled) {
      console.log('Claude Auto Review is disabled in .claude/settings.json.');
      process.exit(0);
    }

    const unreviewed = getUnreviewedFiles(loadState(projectRoot));
    if (unreviewed.length === 0) {
      console.log('Claude Auto Review: no unreviewed changes.');
      process.exit(0);
    }

    const timestamp = new Date().toISOString();
    const reviewId = `rev-${timestamp.replace(/[-:.TZ]/g, '').slice(0, 14)}`;
    const files = unreviewed.map((entry) => entry.file);
    const configuredRules = settings.rulesFile || runtime.rulesPath;
    const rulesPath = path.isAbsolute(configuredRules) ? configuredRules : path.join(projectRoot, configuredRules);
    const rules = readIfExists(rulesPath, readIfExists(runtime.rulesPath));
    const diff = shellGitDiff(files, projectRoot);
    const snapshots = currentFileSnapshots(files, projectRoot);

    const reviewPath = path.join(runtime.baseDir, 'reviews', `review-${reviewId}.md`);
    const promptPath = path.join(runtime.baseDir, 'run', `review-${reviewId}-prompt.md`);
    const prompt = buildPrompt({
      reviewId,
      timestamp,
      files: unreviewed,
      rules,
      diff,
      snapshots,
      reviewPath
    });

    fs.writeFileSync(promptPath, prompt);
    fs.writeFileSync(reviewPath, `# Review ${reviewId} - ${timestamp}

## Files Reviewed
${unreviewed.map((entry) => `- ${entry.file} (hash: ${entry.hash})`).join('\n')}

## Findings

Pending. Claude must complete this review from ${promptPath}.

## Verdict

Pending.
`);

    markFilesReviewed(unreviewed, reviewId, projectRoot);

    console.log(`Claude Auto Review prompt created: ${promptPath}`);
    console.log(`Review file initialized: ${reviewPath}`);
    console.log('Read the prompt, complete the review file, and fix any agreed CRITICAL or HIGH findings before stopping.');
  } catch (error) {
    console.error(`Claude Auto Review failed open: ${error.message}`);
    process.exit(0);
  }
}

main();
