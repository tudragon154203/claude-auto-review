#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { ensureRuntime, getProjectRoot } = require('./state');

function copyIfChanged(source, destination) {
  if (!fs.existsSync(source)) return;
  const content = fs.readFileSync(source, 'utf8');
  if (!fs.existsSync(destination) || fs.readFileSync(destination, 'utf8') !== content) {
    fs.writeFileSync(destination, content);
  }
}

function main() {
  const projectRoot = getProjectRoot();
  const pluginRoot = path.resolve(__dirname, '..');
  const runtime = ensureRuntime(projectRoot, pluginRoot);
  const runtimeScripts = path.join(runtime.baseDir, 'scripts');
  const runtimeAgents = path.join(runtime.baseDir, 'agents');
  fs.mkdirSync(runtimeScripts, { recursive: true });
  fs.mkdirSync(runtimeAgents, { recursive: true });

  fs.writeFileSync(
    path.join(runtimeScripts, 'review-prompt.js'),
    `#!/usr/bin/env node\nrequire(${JSON.stringify(path.relative(runtimeScripts, path.join(pluginRoot, 'scripts', 'review-prompt.js')).split(path.sep).join('/'))});\n`
  );
  copyIfChanged(path.join(pluginRoot, 'agents', 'reviewer.md'), path.join(runtimeAgents, 'reviewer.md'));

  const gitignorePath = path.join(projectRoot, '.gitignore');
  const ignoreEntries = [
    '.claude/claude-auto-review/state.jsonl',
    '.claude/claude-auto-review/run/',
    '.claude/claude-auto-review/reviews/'
  ];
  const existing = fs.existsSync(gitignorePath) ? fs.readFileSync(gitignorePath, 'utf8') : '';
  const missing = ignoreEntries.filter((entry) => !existing.split(/\r?\n/).includes(entry));
  if (missing.length > 0) {
    fs.appendFileSync(gitignorePath, `${existing.endsWith('\n') || existing.length === 0 ? '' : '\n'}${missing.join('\n')}\n`);
  }

  console.log(`Claude Auto Review initialized at ${runtime.baseDir}`);
}

main();
