import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { analyzeFiles, inspectWorkspace, resolveLimits } from './check-bootstrap-budget.mjs';

const limits = { maxChars: 40000, totalMaxChars: 80000 };
const file = (name, content) => ({ name, path: `/fixture/${name}`, content, missing: false });

test('UTF-16 demand and JS trimEnd semantics, including FEFF and U0085', () => {
  const result = analyzeFiles([file('SOUL.md', '😀\u0085\uFEFF\n')], limits);
  assert.equal(result.sourceDemandChars, 3);
  assert.equal(result.sourceHeadroomChars, 79997);
});

test('equality at file and total caps is allowed; one extra unit is detected', () => {
  const exact = [file('AGENTS.md', 'a'.repeat(40000)), file('SOUL.md', 'b'.repeat(40000))];
  assert.equal(analyzeFiles(exact, limits).ok, true);
  assert.equal(analyzeFiles([...exact, file('IDENTITY.md', 'c')], limits).ok, false);
  assert.equal(analyzeFiles([file('AGENTS.md', 'a'.repeat(40001))], limits).ok, false);
});

test('USER has an independent 4000-unit cap', () => {
  assert.equal(analyzeFiles([file('USER.md', 'a'.repeat(4000))], limits).ok, true);
  assert.equal(analyzeFiles([file('USER.md', 'a'.repeat(4001))], limits).issues[0].reason, 'per_file_source_limit');
});

test('a tiny real file is skipped below 64 remaining, but whitespace is not loss', () => {
  const small = { maxChars: 1000, totalMaxChars: 1000 };
  const first = file('AGENTS.md', 'a'.repeat(937));
  assert.equal(analyzeFiles([first, file('SOUL.md', 'x')], small).issues[0].reason, 'minimum_remaining_budget');
  assert.equal(analyzeFiles([first, file('SOUL.md', ' \n')], small).ok, true);
  assert.equal(analyzeFiles([file('AGENTS.md', 'a'.repeat(936)), file('SOUL.md', 'x')], small).ok, true);
});

test('missing placeholders consume capacity, not the real-file 64-unit floor', () => {
  const missing = { name: 'BOOTSTRAP.md', path: '/fixture/BOOTSTRAP.md', missing: true };
  const demand = `[MISSING] Expected at: ${missing.path}`.length;
  assert.equal(analyzeFiles([missing], { maxChars: 1, totalMaxChars: demand }).ok, true);
  assert.equal(analyzeFiles([missing], { maxChars: 1, totalMaxChars: demand - 1 }).ok, false);
});

test('cron never opens MEMORY/BOOTSTRAP; main omits absent optional USER/MEMORY', async () => {
  const opened = [];
  const reader = async (p) => {
    opened.push(path.basename(p));
    if (['USER.md', 'MEMORY.md', 'BOOTSTRAP.md'].includes(path.basename(p))) throw Object.assign(new Error('missing'), { code: 'ENOENT' });
    return 'short';
  };
  const cron = await inspectWorkspace('/fixture', 'cron', limits, reader);
  assert.deepEqual(opened, ['AGENTS.md', 'SOUL.md', 'IDENTITY.md', 'USER.md']);
  assert.equal(cron.ok, true);
  const main = await inspectWorkspace('/fixture', 'main', limits, reader);
  assert.deepEqual(main.files.map((r) => r.name), ['AGENTS.md', 'SOUL.md', 'IDENTITY.md', 'BOOTSTRAP.md']);
  assert.equal(main.files.at(-1).missing, true);
  assert.match(main.scope, /absent BOOTSTRAP placeholder may overstate/);
});

test('defaults and exact per-agent overrides are honored; invalid limits fail', () => {
  assert.deepEqual(resolveLimits({}, 'main'), { maxChars: 20000, totalMaxChars: 60000 });
  assert.deepEqual(resolveLimits({ agents: { defaults: { bootstrapMaxChars: 40000, bootstrapTotalMaxChars: 80000 }, list: [{ id: 'other', bootstrapMaxChars: 1 }, { id: 'main', bootstrapMaxChars: 50000 }] } }, 'main'), { maxChars: 50000, totalMaxChars: 80000 });
  for (const value of [0, -1, '40000', null, Infinity]) {
    if (value === null) continue; // Null uses the runtime's nullish fallback.
    assert.throws(() => resolveLimits({ agents: { defaults: { bootstrapMaxChars: value } } }, 'main'));
  }
});

test('canonical keyed agent caps override legacy lists, with runtime ID normalization', () => {
  const config = { agents: { defaults: { bootstrapMaxChars: 40000, bootstrapTotalMaxChars: 80000 },
    entries: { ' Main ': { bootstrapMaxChars: 7000, bootstrapTotalMaxChars: 10000 } },
    list: [{ id: 'main', bootstrapMaxChars: 50000, bootstrapTotalMaxChars: 90000 }] } };
  assert.deepEqual(resolveLimits(config, 'MAIN'), { maxChars: 7000, totalMaxChars: 10000 });
  config.agents.entries = {};
  assert.deepEqual(resolveLimits(config, 'main'), { maxChars: 40000, totalMaxChars: 80000 });
  config.agents.entries = null;
  assert.throws(() => resolveLimits(config, 'main'));
  delete config.agents.entries;
  config.agents.list[0].id = 'My Agent';
  assert.deepEqual(resolveLimits(config, 'my-agent'), { maxChars: 50000, totalMaxChars: 90000 });
  config.agents.entries = { 'main-': { bootstrapMaxChars: 123 } };
  assert.equal(resolveLimits(config, 'main-').maxChars, 123);
  assert.equal(resolveLimits(config, 'main').maxChars, 40000);
});

test('CLI reports only counts, detects overflow and fails closed without leaking malformed config', async () => {
  const dir = await mkdtemp(path.join(tmpdir(), 'bootstrap-budget-test-'));
  const config = path.join(dir, 'config.json');
  await writeFile(config, JSON.stringify({ agents: { defaults: { bootstrapMaxChars: 40000, bootstrapTotalMaxChars: 80000 } } }));
  const sentinel = 'PRIVATE_SENTINEL_0123456789';
  for (const name of ['AGENTS.md', 'SOUL.md', 'IDENTITY.md', 'USER.md', 'BOOTSTRAP.md', 'MEMORY.md']) await writeFile(path.join(dir, name), sentinel);
  const command = (extra = []) => spawnSync(process.execPath, [new URL('./check-bootstrap-budget.mjs', import.meta.url).pathname, '--workspace', dir, '--config', config, '--json', ...extra], { encoding: 'utf8' });
  const before = await readFile(path.join(dir, 'MEMORY.md'));
  let result = command();
  assert.equal(result.status, 0);
  assert.equal(result.stdout.includes(sentinel), false);
  assert.equal(JSON.parse(result.stdout).projectionOnly, true);
  assert.deepEqual(await readFile(path.join(dir, 'MEMORY.md')), before);
  await writeFile(path.join(dir, 'MEMORY.md'), sentinel.repeat(4000));
  result = command();
  assert.equal(result.status, 2);
  assert.equal(JSON.parse(result.stdout).ok, false);
  assert.equal(command(['--session-kind', 'cron']).status, 0);
  await writeFile(config, `{"SECRET":"${sentinel}", INVALID`);
  result = command();
  assert.equal(result.status, 2);
  assert.equal((result.stdout + result.stderr).includes(sentinel), false);
  assert.equal(result.stdout, '');
});
