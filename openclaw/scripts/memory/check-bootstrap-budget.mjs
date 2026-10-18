#!/usr/bin/env node
/** Counts-only, conservative core-file demand check; never renders file contents. */
import { readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

// Verified against installed OpenClaw 2026.9.8 workspace-bootstrap-policy/bootstrap.
export const MAIN_FILES = ['AGENTS.md', 'SOUL.md', 'IDENTITY.md', 'USER.md', 'BOOTSTRAP.md', 'MEMORY.md'];
export const CRON_FILES = MAIN_FILES.slice(0, 4);
const SCOPE = 'Conservative core-file inventory before setup filtering; not actual injected context. Excludes hooks, extra files, personal USER overlays and provenance filtering. An absent BOOTSTRAP placeholder may overstate completed-workspace demand.';

function normalizeAgentId(value) {
  const normalized = (value ?? '').trim().toLowerCase();
  if (/^[a-z0-9][a-z0-9_-]{0,63}$/.test(normalized)) return normalized;
  return normalized.replace(/[^a-z0-9_-]+/g, '-').replace(/^-+/, '').replace(/-+$/, '').slice(0, 64) || 'main';
}

export function resolveLimits(config, agentId) {
  if (!config || typeof config !== 'object' || Array.isArray(config)) throw new Error('Invalid config object');
  const defaults = config.agents?.defaults ?? {};
  const agents = config.agents ?? {};
  const id = normalizeAgentId(agentId);
  let agent;
  // Canonical keyed entries take precedence even when empty; list is legacy.
  if (Object.hasOwn(agents, 'entries') && agents.entries !== undefined) {
    if (!agents.entries || typeof agents.entries !== 'object' || Array.isArray(agents.entries)) throw new Error('Invalid agent entries');
    agent = Object.entries(agents.entries).find(([key, entry]) => entry && typeof entry === 'object' && !Array.isArray(entry) && normalizeAgentId(key) === id)?.[1];
  } else {
    if (agents.list !== undefined && !Array.isArray(agents.list)) throw new Error('Invalid agent list');
    agent = agents.list?.find((entry) => entry && typeof entry === 'object' && normalizeAgentId(entry.id) === id);
  }
  agent ??= {};
  const limit = (key, fallback) => {
    const value = agent[key] ?? defaults[key] ?? fallback;
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 1) throw new Error(`Invalid ${key}`);
    return Math.floor(value);
  };
  return { maxChars: limit('bootstrapMaxChars', 20000), totalMaxChars: limit('bootstrapTotalMaxChars', 60000) };
}

export function analyzeFiles(files, limits) {
  let sourceDemandChars = 0;
  const issues = [];
  const rows = files.map((file) => {
    const remaining = Math.max(0, limits.totalMaxChars - sourceDemandChars);
    const sourceChars = file.missing ? `[MISSING] Expected at: ${file.path}`.length : file.content.trimEnd().length;
    const perFileLimit = file.name === 'USER.md' ? Math.min(limits.maxChars, 4000) : limits.maxChars;
    if (sourceChars > 0) {
      if (!file.missing && sourceChars > perFileLimit) issues.push({ name: file.name, reason: 'per_file_source_limit' });
      if (!file.missing && remaining < 64) issues.push({ name: file.name, reason: 'minimum_remaining_budget' });
      if (sourceChars > remaining) issues.push({ name: file.name, reason: 'total_source_limit' });
    }
    sourceDemandChars += sourceChars;
    return { name: file.name, missing: file.missing, sourceChars, perFileLimit };
  });
  return {
    ok: issues.length === 0,
    projectionOnly: true,
    scope: SCOPE,
    status: issues.length ? 'core_source_budget_exceeded' : 'core_source_budget_ready',
    ...limits,
    sourceDemandChars,
    sourceHeadroomChars: limits.totalMaxChars - sourceDemandChars,
    files: rows,
    issues,
  };
}

export async function inspectWorkspace(workspace, sessionKind, limits, read = readFile) {
  const files = [];
  for (const name of sessionKind === 'cron' ? CRON_FILES : MAIN_FILES) {
    const filePath = path.join(workspace, name);
    try {
      files.push({ name, path: filePath, missing: false, content: await read(filePath, 'utf8') });
    } catch (error) {
      if (error.code !== 'ENOENT') throw new Error(`Cannot read core file ${name}`);
      // The local runtime omits nonexistent USER/MEMORY, not other core files.
      if (name !== 'USER.md' && name !== 'MEMORY.md') files.push({ name, path: filePath, missing: true });
    }
  }
  return analyzeFiles(files, limits);
}

export async function main(argv = process.argv.slice(2)) {
  try {
    const { values } = parseArgs({ args: argv, options: {
      workspace: { type: 'string', default: fileURLToPath(new URL('../../', import.meta.url)) },
      config: { type: 'string', default: process.env.OPENCLAW_CONFIG_PATH || path.join(homedir(), '.openclaw/openclaw.json') },
      agent: { type: 'string', default: 'main' },
      'session-kind': { type: 'string', default: 'both' },
      json: { type: 'boolean', default: false },
    } });
    if (!['main', 'cron', 'both'].includes(values['session-kind'])) throw new Error('Invalid session-kind');
    let config;
    try { config = JSON.parse(await readFile(values.config, 'utf8')); }
    catch { throw new Error('Cannot read JSON config; no configuration contents reported'); }
    const limits = resolveLimits(config, values.agent);
    const projections = {};
    for (const kind of values['session-kind'] === 'both' ? ['main', 'cron'] : [values['session-kind']]) {
      projections[kind] = await inspectWorkspace(path.resolve(values.workspace), kind, limits);
    }
    const ok = Object.values(projections).every((result) => result.ok);
    const payload = { ok, projectionOnly: true, scope: SCOPE, agent: values.agent, projections,
      message: ok ? 'Core-file source demand fits configured budgets (projection only)' : 'Conservative core-file source demand exceeds a budget; inspect projection before editing owner documents' };
    if (values.json) process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
    else {
      process.stdout.write(`${payload.message}\n${SCOPE}\n`);
      for (const [kind, result] of Object.entries(projections)) process.stdout.write(`${kind}: source demand ${result.sourceDemandChars}/${result.totalMaxChars} UTF-16 units, issues=${result.issues.length}\n`);
    }
    return ok ? 0 : 2;
  } catch (error) {
    // Avoid parser/IO diagnostics containing private source or configuration text.
    process.stderr.write(`BOOTSTRAP_BUDGET_CHECK_FAILED: ${error.message.startsWith('Cannot read core file ') || error.message.startsWith('Invalid bootstrap') ? error.message : 'invalid arguments, configuration or unreadable input'}\n`);
    return 2;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = await main();
