#!/usr/bin/env node
const path = require('path');
const {
  ensureRuntime,
  getProjectRoot,
  getUnreviewedFiles,
  loadSettings,
  loadState
} = require('../scripts/state');

function main() {
  try {
    const projectRoot = getProjectRoot();
    ensureRuntime(projectRoot);
    const settings = loadSettings(projectRoot);
    if (!settings.enabled) process.exit(0);

    const unreviewed = getUnreviewedFiles(loadState(projectRoot));
    if (unreviewed.length === 0) process.exit(0);

    const files = unreviewed.map((entry) => entry.file).join(', ');
    const reviewScript = path.join(projectRoot, '.claude', 'claude-auto-review', 'scripts', 'review-prompt.js');
    const pluginReviewScript = path.join(__dirname, '..', 'scripts', 'review-prompt.js');
    const command = `node "${pluginReviewScript}"`;

    console.log(JSON.stringify({
      block: true,
      message: `Claude Auto Review: Unreviewed changes detected in ${files}.`,
      feedback: `Review required before stopping. Run ${command}, follow the generated review prompt, write the review, and fix any CRITICAL or HIGH findings you agree with. Project-local script path after setup: ${reviewScript}`,
      continue: false
    }));
    process.exit(2);
  } catch (_) {
    process.exit(0);
  }
}

main();
