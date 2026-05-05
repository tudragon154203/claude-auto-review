const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  appendState,
  ensureRuntime,
  extractFilePathsFromHookInput,
  getFileHash,
  getUnreviewedFiles,
  loadState,
  markFilesReviewed,
  normalizeRelativePath,
  wasHashReviewed
} = require('../scripts/state');

function tempProject() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'claude-auto-review-'));
}

describe('state management', () => {
  it('normalizes paths inside the project root', () => {
    const projectRoot = tempProject();
    expect(normalizeRelativePath('src/app.ts', projectRoot)).toBe('src/app.ts');
    expect(normalizeRelativePath(path.join(projectRoot, 'src', 'app.ts'), projectRoot)).toBe('src/app.ts');
    expect(normalizeRelativePath(path.join(projectRoot, '..', 'outside.ts'), projectRoot)).toBeNull();
  });

  it('hashes existing file content', () => {
    const projectRoot = tempProject();
    fs.mkdirSync(path.join(projectRoot, 'src'));
    fs.writeFileSync(path.join(projectRoot, 'src', 'app.ts'), 'export const value = 1;\n');
    expect(getFileHash('src/app.ts', projectRoot)).toMatch(/^[a-f0-9]{8}$/);
  });

  it('loads latest unreviewed file entries', () => {
    const projectRoot = tempProject();
    ensureRuntime(projectRoot);
    appendState({ type: 'edit', file: 'a.ts', hash: '11111111', timestamp: '2026-05-05T01:00:00.000Z', reviewed: false }, projectRoot);
    appendState({ type: 'edit', file: 'a.ts', hash: '22222222', timestamp: '2026-05-05T02:00:00.000Z', reviewed: true, reviewId: 'rev-1' }, projectRoot);
    appendState({ type: 'edit', file: 'b.ts', hash: '33333333', timestamp: '2026-05-05T03:00:00.000Z', reviewed: false }, projectRoot);

    expect(getUnreviewedFiles(loadState(projectRoot))).toEqual([
      expect.objectContaining({ file: 'b.ts', hash: '33333333' })
    ]);
  });

  it('recognizes hashes reviewed in earlier entries', () => {
    const projectRoot = tempProject();
    ensureRuntime(projectRoot);
    const entry = { type: 'edit', file: 'a.ts', hash: '11111111', timestamp: '2026-05-05T01:00:00.000Z', reviewed: false };
    markFilesReviewed([entry], 'rev-1', projectRoot);
    expect(wasHashReviewed(loadState(projectRoot), 'a.ts', '11111111')).toBe(true);
  });

  it('extracts paths from Claude hook payload shapes', () => {
    expect(extractFilePathsFromHookInput({ file_path: 'a.ts' })).toEqual(['a.ts']);
    expect(extractFilePathsFromHookInput({ tool_input: { file_path: 'b.ts' } })).toEqual(['b.ts']);
    expect(extractFilePathsFromHookInput({ tool_input: { edits: [{ file_path: 'c.ts' }, { path: 'd.ts' }] } })).toEqual(['c.ts', 'd.ts']);
  });
});
