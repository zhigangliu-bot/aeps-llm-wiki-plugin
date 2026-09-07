#!/usr/bin/env node
/**
 * check.js - SessionStart auto-update check for aeps-llm-wiki-plugin.
 *
 * Detects whether the local plugin clone is behind origin/HEAD. If so, runs
 * `git pull --ff-only origin main` and reports the outcome via stdout using
 * the Claude Code hook JSON protocol.
 *
 * Usage:
 *   node scripts/update-check/check.js                (hook mode; JSON stdout)
 *   node scripts/update-check/check.js --check-only   (CLI; text stdout, exit 0/1/2)
 *   node scripts/update-check/check.js --pull         (CLI; text stdout, exit 0/1/2)
 *
 * Exit codes (CLI mode):
 *   0 - no update available (or hook ran and nothing to report)
 *   1 - update detected (regardless of whether pull ran)
 *   2 - detection failed (git missing, plugin.json missing version, etc.)
 *
 * Exit codes (hook mode):
 *   0 - always; failures are swallowed silently per design §1.3.
 */

import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import path from 'node:path';

// ---------------------------------------------------------------------------
// Pure functions (exported for tests)
// ---------------------------------------------------------------------------

/**
 * Parse `version` from plugin.json text. Returns null on any failure.
 * Does NOT throw; any parse error → null.
 */
export function parseVersion(jsonText) {
  if (typeof jsonText !== 'string' || jsonText.length === 0) return null;
  try {
    const obj = JSON.parse(jsonText);
    if (obj && typeof obj.version === 'string' && obj.version.length > 0) {
      return obj.version;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Compare two semver strings. Returns:
 *   -1 if a < b
 *    0 if a == b
 *    1 if a > b
 *   null if either is not a valid semver (treated as incomparable)
 *
 * Valid semver: major.minor.patch where each component is a non-negative
 * integer. Pre-release / build metadata are NOT supported (we only compare
 * plugin versions which use plain X.Y.Z).
 */
export function compareSemver(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return null;
  const pa = parseSemverTriplet(a);
  const pb = parseSemverTriplet(b);
  if (!pa || !pb) return null;
  for (let i = 0; i < 3; i++) {
    if (pa[i] < pb[i]) return -1;
    if (pa[i] > pb[i]) return 1;
  }
  return 0;
}

function parseSemverTriplet(s) {
  const m = /^(\d+)\.(\d+)\.(\d+)$/.exec(s);
  if (!m) return null;
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

/**
 * Compare two commit SHAs. Returns true iff they are equal AND both look like
 * hex strings of length >= 7. Empty / null / different-length hex → false.
 *
 * This is a conservative equality check; we do NOT want to declare "equal"
 * on missing data.
 */
export function shasEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const ta = a.trim();
  const tb = b.trim();
  if (ta.length === 0 || tb.length === 0) return false;
  if (ta.length !== tb.length) return false;
  // Case-insensitive compare (git SHAs are conventionally lowercase, but be safe)
  return ta.toLowerCase() === tb.toLowerCase();
}

/**
 * Build the "upgrade success" additionalContext message.
 * Format matches design §3.3 / PRD R3.1 exactly.
 */
export function buildUpgradedMessage(localVer, remoteVer) {
  return `📦 aeps-llm-wiki 已升级(${localVer} → ${remoteVer})。当前 session 仍使用旧代码,运行 \`/reload-plugins\` 后生效。`;
}

/**
 * Build the "pull failed" additionalContext message.
 * Truncates the reason to 80 chars max (with `…` suffix if truncated).
 * Format matches design §3.3 / PRD R3.2 exactly.
 */
export function buildPullFailedMessage(reason, pluginRoot) {
  const truncated = truncateReason(reason, 80);
  return `⚠️ aeps-llm-wiki 有新版本但自动升级失败(原因:${truncated})。请手动处理:在 plugin 根目录跑 \`git pull --ff-only origin main\`,或重新 \`/plugin install aeps-llm-wiki@aeps-public-marketplace\`。`;
}

/**
 * Truncate a reason string to at most `max` chars. Picks first non-empty line
 * of input; appends `…` if the line was longer than max.
 */
export function truncateReason(reason, max) {
  if (typeof reason !== 'string') return '未知原因';
  const firstLine = reason.split(/\r?\n/).find((l) => l.trim().length > 0) ?? '';
  const trimmed = firstLine.trim();
  if (trimmed.length === 0) return '未知原因';
  if (trimmed.length <= max) return trimmed;
  return trimmed.slice(0, max - 1) + '…';
}

/**
 * Message emitted after a divergent cache was successfully reset to
 * origin/main (i.e. the force-push rewrite case). Same shape as the upgrade
 * message but explains the reset rather than a fast-forward pull.
 */
export function buildDivergedResetMessage(localVer, remoteVer) {
  return `📦 aeps-llm-wiki 远端历史被改写(force-push),已重置到最新版本(${localVer} → ${remoteVer})。当前 session 仍使用旧代码,运行 \`/reload-plugins\` 后生效。`;
}

/**
 * Message emitted when divergent cache could not be reset (e.g. dirty
 * working tree blocked the reset). User needs to take manual action.
 */
export function buildDivergedResetFailedMessage(reason) {
  const truncated = truncateReason(reason, 80);
  return `⚠️ aeps-llm-wiki 远端历史被改写(force-push),本地 cache 跟远端已分叉(原因:${truncated})。请手动处理:卸载后重装 plugin(\`/plugin uninstall aeps-llm-wiki@aeps-public-marketplace\` 然后 \`/plugin install aeps-llm-wiki@aeps-public-marketplace\`),或手动进 plugin 仓跑 \`git fetch && git reset --hard origin/main\`。`;
}

/**
 * Build the hook JSON output for additionalContext injection.
 * Returns the JSON string with a single trailing newline (Claude Code accepts
 * either with or without newline; we add one for shell-friendliness).
 */
export function buildHookOutput(additionalContext) {
  return JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext,
    },
  }) + '\n';
}

/**
 * Parse the first line of `git ls-remote origin HEAD` output.
 * Format: `<sha>\tHEAD\n`. We split on whitespace and take [0].
 * Returns null on any parse failure.
 */
export function parseLsRemoteHead(stdout) {
  if (typeof stdout !== 'string' || stdout.length === 0) return null;
  const firstLine = stdout.split(/\r?\n/)[0] ?? '';
  const parts = firstLine.split(/\s+/);
  if (parts.length === 0) return null;
  const sha = parts[0].trim();
  if (sha.length === 0) return null;
  return sha;
}

/**
 * Parse `git rev-parse HEAD` output. Returns the trimmed SHA or null.
 */
export function parseRevParseHead(stdout) {
  if (typeof stdout !== 'string' || stdout.length === 0) return null;
  const sha = stdout.split(/\r?\n/)[0]?.trim() ?? '';
  if (sha.length === 0) return null;
  return sha;
}

// ---------------------------------------------------------------------------
// Shell helpers
// ---------------------------------------------------------------------------

/**
 * Run `git` with given args in `cwd`. Returns { stdout, stderr, status }.
 * NEVER throws; if git is not on PATH, status is null and stderr contains
 * the ENOENT-style error from Node.
 *
 * We use spawnSync with a 10s timeout per call to bound total runtime.
 */
function git(cwd, args) {
  return spawnSync('git', args, {
    cwd,
    encoding: 'utf8',
    timeout: 10000,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}

// ---------------------------------------------------------------------------
// Decision state (returned by detect(), consumed by callers)
// ---------------------------------------------------------------------------

// Possible states:
//   'no-update'        - local SHA == remote SHA
//   'updated'          - pull succeeded
//   'pull-failed'      - pull rejected (e.g. dirty tree, conflict)
//   'detect-failed'    - any other failure (git missing, plugin.json broken, etc.)

// ---------------------------------------------------------------------------
// Main flow
// ---------------------------------------------------------------------------

/**
 * Detect whether the local clone is behind origin/HEAD.
 *
 * If `shouldPull` is true, attempts `git pull --ff-only origin main` when
 * remote is ahead; otherwise just returns the SHA-mismatch signal.
 */
async function detect(pluginRoot, { shouldPull = true } = {}) {
  // 1. Read plugin.json
  let localVer;
  try {
    const manifestPath = path.join(pluginRoot, '.claude-plugin', 'plugin.json');
    const text = await readFile(manifestPath, 'utf8');
    localVer = parseVersion(text);
  } catch {
    return { state: 'detect-failed', reason: 'plugin.json read failed' };
  }
  if (!localVer) {
    return { state: 'detect-failed', reason: 'plugin.json missing version field' };
  }

  // 2. Local HEAD SHA
  const rev = git(pluginRoot, ['rev-parse', 'HEAD']);
  if (rev.status !== 0 || !rev.stdout) {
    return { state: 'detect-failed', reason: 'git rev-parse HEAD failed' };
  }
  const localSha = parseRevParseHead(rev.stdout);
  if (!localSha) {
    return { state: 'detect-failed', reason: 'git rev-parse HEAD returned empty SHA' };
  }

  // 3. Remote HEAD SHA (ls-remote is a non-mutating query)
  const ls = git(pluginRoot, ['ls-remote', 'origin', 'HEAD']);
  if (ls.status !== 0 || !ls.stdout) {
    return { state: 'detect-failed', reason: 'git ls-remote origin HEAD failed' };
  }
  const remoteSha = parseLsRemoteHead(ls.stdout);
  if (!remoteSha) {
    return { state: 'detect-failed', reason: 'git ls-remote origin HEAD returned empty SHA' };
  }

  // 4. Compare
  if (shasEqual(localSha, remoteSha)) {
    return { state: 'no-update', localVer, remoteVer: localVer };
  }

  // SHA differs. Caller decides whether to actually pull.
  if (!shouldPull) {
    return { state: 'update-available', localVer, remoteVer: localVer };
  }

  // 5. Pull --ff-only
  const pull = git(pluginRoot, ['pull', '--ff-only', 'origin', 'main']);
  if (pull.status !== 0) {
    const pullReason = (pull.stderr && pull.stderr.length > 0) ? pull.stderr : (pull.stdout || 'git pull failed');
    // Any pull --ff-only failure → fallback to fetch + reset --hard origin/main.
    // This covers three real cases:
    //   a) Force-push rewrite of remote history (cache no longer fast-forwards)
    //   b) Cache remote URL unreachable mid-session (auth/network)
    //   c) Local cache has untracked files that block pull
    // In case (c) reset --hard will refuse; we then report back so the user
    // can take manual action.
    const fetch = git(pluginRoot, ['fetch', 'origin', 'main']);
    if (fetch.status === 0) {
      const reset = git(pluginRoot, ['reset', '--hard', 'origin/main']);
      if (reset.status === 0) {
        // After reset, re-read plugin.json for the post-reset version.
        let resetVer = localVer;
        try {
          const manifestPath = path.join(pluginRoot, '.claude-plugin', 'plugin.json');
          const text = await readFile(manifestPath, 'utf8');
          const v = parseVersion(text);
          if (v) resetVer = v;
        } catch {
          // keep localVer
        }
        return { state: 'diverged-reset', localVer, remoteVer: resetVer };
      }
      const resetReason = (reset.stderr && reset.stderr.length > 0) ? reset.stderr : (reset.stdout || 'git reset failed');
      return { state: 'diverged-reset-failed', reason: resetReason };
    }
    const fetchReason = (fetch.stderr && fetch.stderr.length > 0) ? fetch.stderr : (fetch.stdout || 'git fetch failed');
    // If even fetch failed (e.g. SSH auth down), report the original pull
    // failure reason so the user sees the real blocker.
    return { state: 'pull-failed', reason: pullReason || fetchReason };
  }

  // 6. Re-read plugin.json to get the post-pull version
  let remoteVer = localVer;
  try {
    const manifestPath = path.join(pluginRoot, '.claude-plugin', 'plugin.json');
    const text = await readFile(manifestPath, 'utf8');
    const v = parseVersion(text);
    if (v) remoteVer = v;
  } catch {
    // Stick with old version string if re-read fails
  }

  return { state: 'updated', localVer, remoteVer };
}

/**
 * Hook-mode main: prints JSON to stdout (or nothing) and always exits 0.
 */
async function runHook() {
  const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT;
  if (!pluginRoot || pluginRoot.length === 0) {
    // Misuse (env var not set) → silent exit
    return;
  }

  const result = await detect(pluginRoot);

  if (result.state === 'updated') {
    const msg = buildUpgradedMessage(result.localVer, result.remoteVer);
    process.stdout.write(buildHookOutput(msg));
  } else if (result.state === 'diverged-reset') {
    const msg = buildDivergedResetMessage(result.localVer, result.remoteVer);
    process.stdout.write(buildHookOutput(msg));
  } else if (result.state === 'pull-failed') {
    const msg = buildPullFailedMessage(result.reason, pluginRoot);
    process.stdout.write(buildHookOutput(msg));
  } else if (result.state === 'diverged-reset-failed') {
    const msg = buildDivergedResetFailedMessage(result.reason);
    process.stdout.write(buildHookOutput(msg));
  }
  // 'no-update' and 'detect-failed' → silent
}

/**
 * CLI-mode main: prints plain text and returns an exit code.
 */
async function runCli(mode) {
  const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT;
  if (!pluginRoot || pluginRoot.length === 0) {
    process.stdout.write('error: CLAUDE_PLUGIN_ROOT is not set\n');
    process.exit(2);
  }

  // --check-only: detect only, do not pull
  // --pull: detect + pull (default for hook mode)
  const shouldPull = mode !== '--check-only';
  const result = await detect(pluginRoot, { shouldPull });

  if (result.state === 'no-update') {
    process.stdout.write('no-update\n');
    process.exit(0);
  }
  if (result.state === 'update-available') {
    process.stdout.write(`update-available: local=${result.localVer}\n`);
    process.exit(1);
  }
  if (result.state === 'detect-failed') {
    process.stdout.write(`detect-failed: ${result.reason}\n`);
    process.exit(2);
  }
  if (result.state === 'updated') {
    process.stdout.write(`updated: ${result.localVer} → ${result.remoteVer}\n`);
    process.exit(0);
  }
  if (result.state === 'pull-failed') {
    process.stdout.write(`pull-failed: ${truncateReason(result.reason, 200)}\n`);
    process.exit(1);
  }

  // Defensive fallback (should not reach here)
  process.exit(2);
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

async function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--check-only')) {
    await runCli('--check-only');
    return;
  }
  if (argv.includes('--pull')) {
    await runCli('--pull');
    return;
  }
  await runHook();
}

// ANY throw → silent exit 0 (design §1.3 total rule)
main().catch(() => process.exit(0));
