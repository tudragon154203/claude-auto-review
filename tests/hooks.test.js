const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { loadState } = require('../scripts/state');

const repoRoot = path.resolve(__dirname, '..');

function tempProject() {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-auto-review-hooks-'));
  fs.mkdirSync(path.join(projectRoot, 'src'), { recursive: true });
  return projectRoot;
}

function runNode(script, projectRoot, input = '') {
  return spawnSync(process.execPath, [path.join(repoRoot, script)], {
    cwd: projectRoot,
    input,
    encoding: 'utf8',
    env: {
      ...process.env,
      CLAUDE_PROJECT_DIR: projectRoot
    }
  });
}

describe('hooks', () => {
  it('post-tool-use logs changed files and stop hook blocks', () => {
    const projectRoot = tempProject();
    fs.writeFileSync(path.join(projectRoot, 'src', 'app.ts'), 'export const value = 1;\n');

    const post = runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({ tool_input: { file_path: 'src/app.ts' } }));
    expect(post.status).toBe(0);
    expect(loadState(projectRoot)).toEqual([
      expect.objectContaining({ file: 'src/app.ts', reviewed: false })
    ]);

    const stop = runNode('hooks/stop-hook.js', projectRoot);
    expect(stop.status).toBe(2);
    expect(JSON.parse(stop.stdout).block).toBe(true);
  });

  it('review-prompt creates prompt and allows later stop', () => {
    const projectRoot = tempProject();
    fs.writeFileSync(path.join(projectRoot, 'src', 'app.ts'), 'export const value = 1;\n');
    runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({ file_path: 'src/app.ts' }));

    const review = runNode('scripts/review-prompt.js', projectRoot);
    expect(review.status).toBe(0);
    expect(fs.readdirSync(path.join(projectRoot, '.claude', 'claude-auto-review', 'run')).length).toBe(1);
    expect(fs.readdirSync(path.join(projectRoot, '.claude', 'claude-auto-review', 'reviews')).length).toBe(1);

    const stop = runNode('hooks/stop-hook.js', projectRoot);
    expect(stop.status).toBe(0);
  });

  it('fails open for invalid hook input', () => {
    const projectRoot = tempProject();
    const post = runNode('hooks/post-tool-use.js', projectRoot, '{not-json');
    expect(post.status).toBe(0);
  });

  it('does not track files skipped by extension', () => {
    const projectRoot = tempProject();
    fs.mkdirSync(path.join(projectRoot, '.claude'), { recursive: true });
    fs.writeFileSync(path.join(projectRoot, '.claude', 'settings.json'), JSON.stringify({
      'claude-auto-review': {
        skipExtensions: ['.MD']
      }
    }));
    fs.writeFileSync(path.join(projectRoot, 'README.md'), '# docs\n');

    const post = runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({ file_path: 'README.md' }));
    expect(post.status).toBe(0);
    expect(loadState(projectRoot)).toEqual([]);

    const stop = runNode('hooks/stop-hook.js', projectRoot);
    expect(stop.status).toBe(0);
  });

  it('allows stop when disabled in project settings', () => {
    const projectRoot = tempProject();
    fs.mkdirSync(path.join(projectRoot, '.claude'), { recursive: true });
    fs.writeFileSync(path.join(projectRoot, '.claude', 'settings.json'), JSON.stringify({
      'claude-auto-review': {
        enabled: false
      }
    }));
    fs.writeFileSync(path.join(projectRoot, 'src', 'app.ts'), 'export const value = 1;\n');

    const post = runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({ file_path: 'src/app.ts' }));
    expect(post.status).toBe(0);
    expect(loadState(projectRoot)).toEqual([]);

    const stop = runNode('hooks/stop-hook.js', projectRoot);
    expect(stop.status).toBe(0);
  });

  it('treats a previously reviewed identical hash as already reviewed', () => {
    const projectRoot = tempProject();
    fs.writeFileSync(path.join(projectRoot, 'src', 'app.ts'), 'export const value = 1;\n');
    runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({ file_path: 'src/app.ts' }));
    runNode('scripts/review-prompt.js', projectRoot);

    const postAgain = runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({ file_path: 'src/app.ts' }));
    expect(postAgain.status).toBe(0);
    expect(loadState(projectRoot).at(-1)).toEqual(expect.objectContaining({
      file: 'src/app.ts',
      reviewed: true
    }));

    const stop = runNode('hooks/stop-hook.js', projectRoot);
    expect(stop.status).toBe(0);
  });

  it('re-blocks after a reviewed file changes to a new hash', () => {
    const projectRoot = tempProject();
    fs.writeFileSync(path.join(projectRoot, 'src', 'app.ts'), 'export const value = 1;\n');
    runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({ file_path: 'src/app.ts' }));
    runNode('scripts/review-prompt.js', projectRoot);

    fs.writeFileSync(path.join(projectRoot, 'src', 'app.ts'), 'export const value = 2;\n');
    runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({ file_path: 'src/app.ts' }));

    const stop = runNode('hooks/stop-hook.js', projectRoot);
    expect(stop.status).toBe(2);
    expect(JSON.parse(stop.stdout).message).toContain('src/app.ts');
  });

  it('tracks multiple files from a MultiEdit-style payload', () => {
    const projectRoot = tempProject();
    fs.writeFileSync(path.join(projectRoot, 'src', 'a.ts'), 'export const a = 1;\n');
    fs.writeFileSync(path.join(projectRoot, 'src', 'b.ts'), 'export const b = 1;\n');

    const post = runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({
      tool_input: {
        edits: [
          { file_path: 'src/a.ts' },
          { file_path: 'src/b.ts' }
        ]
      }
    }));

    expect(post.status).toBe(0);
    expect(loadState(projectRoot).map((entry) => entry.file).sort()).toEqual(['src/a.ts', 'src/b.ts']);
    const stop = runNode('hooks/stop-hook.js', projectRoot);
    expect(stop.status).toBe(2);
  });

  it('includes real git diff content in the generated review prompt', () => {
    const projectRoot = tempProject();
    fs.writeFileSync(path.join(projectRoot, 'src', 'app.ts'), 'export const value = 1;\n');
    spawnSync('git', ['init'], { cwd: projectRoot, encoding: 'utf8' });
    spawnSync('git', ['config', 'user.email', 'test@example.com'], { cwd: projectRoot, encoding: 'utf8' });
    spawnSync('git', ['config', 'user.name', 'Tester'], { cwd: projectRoot, encoding: 'utf8' });
    spawnSync('git', ['add', 'src/app.ts'], { cwd: projectRoot, encoding: 'utf8' });
    spawnSync('git', ['commit', '-m', 'init'], { cwd: projectRoot, encoding: 'utf8' });

    fs.writeFileSync(path.join(projectRoot, 'src', 'app.ts'), 'export const value = 2;\n');
    runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({ file_path: 'src/app.ts' }));
    const review = runNode('scripts/review-prompt.js', projectRoot);
    expect(review.status).toBe(0);

    const promptName = fs.readdirSync(path.join(projectRoot, '.claude', 'claude-auto-review', 'run'))[0];
    const prompt = fs.readFileSync(path.join(projectRoot, '.claude', 'claude-auto-review', 'run', promptName), 'utf8');
    expect(prompt).toContain('-export const value = 1;');
    expect(prompt).toContain('+export const value = 2;');
  });

  it('includes snapshots for untracked files when git diff is empty', () => {
    const projectRoot = tempProject();
    fs.writeFileSync(path.join(projectRoot, 'src', 'new.ts'), 'export const created = true;\n');
    spawnSync('git', ['init'], { cwd: projectRoot, encoding: 'utf8' });

    runNode('hooks/post-tool-use.js', projectRoot, JSON.stringify({ file_path: 'src/new.ts' }));
    const review = runNode('scripts/review-prompt.js', projectRoot);
    expect(review.status).toBe(0);

    const promptName = fs.readdirSync(path.join(projectRoot, '.claude', 'claude-auto-review', 'run'))[0];
    const prompt = fs.readFileSync(path.join(projectRoot, '.claude', 'claude-auto-review', 'run', promptName), 'utf8');
    expect(prompt).toContain('## Current File Snapshots');
    expect(prompt).toContain('export const created = true;');
  });

  it('setup script creates runtime shims, agents, rules, and gitignore entries', () => {
    const projectRoot = tempProject();
    const setup = runNode('scripts/setup-claude-auto-review.js', projectRoot);
    expect(setup.status).toBe(0);

    expect(fs.existsSync(path.join(projectRoot, '.claude', 'claude-auto-review', 'scripts', 'review-prompt.js'))).toBe(true);
    expect(fs.existsSync(path.join(projectRoot, '.claude', 'claude-auto-review', 'agents', 'reviewer.md'))).toBe(true);
    expect(fs.existsSync(path.join(projectRoot, '.claude', 'claude-auto-review', 'rules.md'))).toBe(true);
    expect(fs.readFileSync(path.join(projectRoot, '.gitignore'), 'utf8')).toContain('.claude/claude-auto-review/state.jsonl');
  });
});
