#!/usr/bin/env node
const {
  appendState,
  ensureRuntime,
  extractFilePathsFromHookInput,
  getFileHash,
  getProjectRoot,
  loadSettings,
  loadState,
  normalizeRelativePath,
  shouldSkipFile,
  wasHashReviewed
} = require('../scripts/state');

function readStdin() {
  return new Promise((resolve) => {
    let input = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => {
      input += chunk;
    });
    process.stdin.on('end', () => resolve(input));
  });
}

async function main() {
  try {
    const projectRoot = getProjectRoot();
    ensureRuntime(projectRoot);
    const settings = loadSettings(projectRoot);
    if (!settings.enabled) process.exit(0);

    const raw = await readStdin();
    const payload = raw.trim() ? JSON.parse(raw) : {};
    const state = loadState(projectRoot);
    const timestamp = new Date().toISOString();

    for (const candidate of extractFilePathsFromHookInput(payload)) {
      const file = normalizeRelativePath(candidate, projectRoot);
      if (!file || shouldSkipFile(file, settings)) continue;
      const hash = getFileHash(file, projectRoot);
      if (!hash) continue;
      appendState({
        type: 'edit',
        file,
        hash,
        timestamp,
        reviewed: wasHashReviewed(state, file, hash)
      }, projectRoot);
    }

    process.exit(0);
  } catch (_) {
    process.exit(0);
  }
}

main();
