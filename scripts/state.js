const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const STATE_RELATIVE_PATH = path.join('.claude', 'claude-auto-review', 'state.jsonl');
const RUNTIME_DIR = path.join('.claude', 'claude-auto-review');
const DEFAULT_SETTINGS = {
  enabled: true,
  rulesFile: path.join('.claude', 'claude-auto-review', 'rules.md'),
  skipExtensions: [],
  minSeverity: 'MEDIUM',
  autoFix: true
};

function getProjectRoot() {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}

function getPluginRoot() {
  return path.resolve(__dirname, '..');
}

function toPosixPath(value) {
  return value.split(path.sep).join('/');
}

function normalizeRelativePath(filePath, projectRoot = getProjectRoot()) {
  if (!filePath || typeof filePath !== 'string') return null;
  const withoutFileUrl = filePath.startsWith('file://') ? filePath.slice('file://'.length) : filePath;
  const resolved = path.isAbsolute(withoutFileUrl)
    ? path.normalize(withoutFileUrl)
    : path.resolve(projectRoot, withoutFileUrl);
  const relative = path.relative(projectRoot, resolved);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) return null;
  return toPosixPath(relative);
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function getStatePath(projectRoot = getProjectRoot()) {
  return path.join(projectRoot, STATE_RELATIVE_PATH);
}

function readJsonIfExists(filePath) {
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function loadSettings(projectRoot = getProjectRoot()) {
  const settingsPath = path.join(projectRoot, '.claude', 'settings.json');
  try {
    const settings = readJsonIfExists(settingsPath);
    return {
      ...DEFAULT_SETTINGS,
      ...(settings && settings['claude-auto-review'] ? settings['claude-auto-review'] : {})
    };
  } catch (_) {
    return { ...DEFAULT_SETTINGS };
  }
}

function shouldSkipFile(filePath, settings = DEFAULT_SETTINGS) {
  const ext = path.extname(filePath).replace(/^\./, '').toLowerCase();
  const skipExtensions = Array.isArray(settings.skipExtensions)
    ? settings.skipExtensions.map((value) => String(value).replace(/^\./, '').toLowerCase())
    : [];
  return Boolean(ext && skipExtensions.includes(ext));
}

function getFileHash(filePath, projectRoot = getProjectRoot()) {
  const relative = normalizeRelativePath(filePath, projectRoot);
  if (!relative) return null;
  const fullPath = path.join(projectRoot, relative);
  if (!fs.existsSync(fullPath) || !fs.statSync(fullPath).isFile()) return null;
  const content = fs.readFileSync(fullPath);
  return crypto.createHash('sha256').update(content).digest('hex').slice(0, 8);
}

function loadState(projectRoot = getProjectRoot()) {
  const statePath = getStatePath(projectRoot);
  if (!fs.existsSync(statePath)) return [];
  return fs.readFileSync(statePath, 'utf8')
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch (_) {
        return null;
      }
    })
    .filter(Boolean);
}

function appendState(entry, projectRoot = getProjectRoot()) {
  const statePath = getStatePath(projectRoot);
  ensureDir(path.dirname(statePath));
  fs.appendFileSync(statePath, `${JSON.stringify(entry)}\n`);
}

function latestEntriesByFile(state) {
  const latest = new Map();
  for (const entry of state) {
    if (!entry || entry.type !== 'edit' || !entry.file || !entry.hash) continue;
    const current = latest.get(entry.file);
    if (!current || new Date(entry.timestamp) >= new Date(current.timestamp)) {
      latest.set(entry.file, entry);
    }
  }
  return latest;
}

function reviewedHashesByFile(state) {
  const reviewed = new Map();
  for (const entry of state) {
    if (!entry || entry.type !== 'edit' || !entry.file || !entry.hash || !entry.reviewed) continue;
    const hashes = reviewed.get(entry.file) || new Set();
    hashes.add(entry.hash);
    reviewed.set(entry.file, hashes);
  }
  return reviewed;
}

function wasHashReviewed(state, file, hash) {
  const reviewed = reviewedHashesByFile(state);
  return Boolean(reviewed.get(file) && reviewed.get(file).has(hash));
}

function getUnreviewedFiles(state) {
  return [...latestEntriesByFile(state).values()].filter((entry) => !entry.reviewed);
}

function markFilesReviewed(entries, reviewId, projectRoot = getProjectRoot()) {
  const timestamp = new Date().toISOString();
  for (const entry of entries) {
    appendState({
      type: 'edit',
      file: entry.file,
      hash: entry.hash,
      timestamp,
      reviewed: true,
      reviewId
    }, projectRoot);
  }
}

function extractFilePathsFromHookInput(input) {
  const candidates = [];
  const toolInput = input && typeof input === 'object' && input.tool_input ? input.tool_input : input;

  function add(value) {
    if (typeof value === 'string' && value.trim()) candidates.push(value);
  }

  if (toolInput && typeof toolInput === 'object') {
    add(toolInput.file_path);
    add(toolInput.path);
    add(toolInput.filePath);
    if (Array.isArray(toolInput.edits)) {
      for (const edit of toolInput.edits) {
        if (edit && typeof edit === 'object') {
          add(edit.file_path);
          add(edit.path);
          add(edit.filePath);
        }
      }
    }
  }

  return [...new Set(candidates)];
}

function ensureRuntime(projectRoot = getProjectRoot(), pluginRoot = getPluginRoot()) {
  const baseDir = path.join(projectRoot, RUNTIME_DIR);
  ensureDir(baseDir);
  ensureDir(path.join(baseDir, 'reviews'));
  ensureDir(path.join(baseDir, 'run'));
  const statePath = getStatePath(projectRoot);
  if (!fs.existsSync(statePath)) fs.writeFileSync(statePath, '');

  const rulesPath = path.join(baseDir, 'rules.md');
  if (!fs.existsSync(rulesPath)) {
    const defaultRulesPath = path.join(pluginRoot, 'rules', 'default-rules.md');
    const fallback = '# Claude Auto Review Rules\n\n- Review semantic correctness, security, and maintainability.\n';
    fs.writeFileSync(rulesPath, fs.existsSync(defaultRulesPath) ? fs.readFileSync(defaultRulesPath, 'utf8') : fallback);
  }

  return { baseDir, statePath, rulesPath };
}

module.exports = {
  DEFAULT_SETTINGS,
  RUNTIME_DIR,
  STATE_RELATIVE_PATH,
  appendState,
  ensureRuntime,
  extractFilePathsFromHookInput,
  getFileHash,
  getPluginRoot,
  getProjectRoot,
  getStatePath,
  getUnreviewedFiles,
  loadSettings,
  loadState,
  markFilesReviewed,
  normalizeRelativePath,
  shouldSkipFile,
  wasHashReviewed
};
