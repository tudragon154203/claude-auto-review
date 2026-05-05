const fs = require('fs');
const os = require('os');
const path = require('path');
const { ensureRuntime, loadSettings, shouldSkipFile } = require('../scripts/state');

describe('rules and settings', () => {
  it('initializes project rules from default rules', () => {
    const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-auto-review-rules-'));
    const runtime = ensureRuntime(projectRoot, path.resolve(__dirname, '..'));
    expect(fs.readFileSync(runtime.rulesPath, 'utf8')).toContain('# Claude Auto Review Rules');
  });

  it('loads project settings and applies skip extensions', () => {
    const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-auto-review-settings-'));
    fs.mkdirSync(path.join(projectRoot, '.claude'), { recursive: true });
    fs.writeFileSync(path.join(projectRoot, '.claude', 'settings.json'), JSON.stringify({
      'claude-auto-review': {
        skipExtensions: ['.MD']
      }
    }));

    const settings = loadSettings(projectRoot);
    expect(shouldSkipFile('README.md', settings)).toBe(true);
    expect(shouldSkipFile('src/app.ts', settings)).toBe(false);
  });
});
