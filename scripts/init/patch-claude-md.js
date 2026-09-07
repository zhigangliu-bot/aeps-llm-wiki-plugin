#!/usr/bin/env node
/**
 * patch-claude-md.js - Idempotent management of CLAUDE.md controlled block.
 *
 * Algorithm:
 *   1. If file doesn't exist → create with the controlled block at end.
 *   2. If file exists:
 *      a. Try to match controlled block regex:
 *         <!-- aeps-llm-wiki-plugin:start -->[\s\S]*?<!-- aeps-llm-wiki-plugin:end -->
 *      b. If matched and content equals canonical block → SKIP (no-op)
 *      c. If matched but content differs → REPLACE the block in place
 *      d. If NOT matched → check for old start/end markers (legacy); if found → REPLACE
 *      e. If no markers at all → APPEND canonical block to end of file
 *
 * The regex match MUST succeed for legacy detection; if user manually edits the
 * start/end marker text, the script exits with error (per implement-init.md §6.1).
 *
 * Usage:
 *   node scripts/init/patch-claude-md.js --project <dir> [--dry-run]
 *
 * Exit codes: 0 ok / 1 invalid args / 3 marker mismatch (user-edited start/end)
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const CONTROLLED_BLOCK = `<!-- aeps-llm-wiki-plugin:start -->
## Wiki 工作流

你的身份是一个汽车电子软件工程师、架构师,开始任何工作前，先读取 \`schema/schema.md\`，并遵循其中的工作流与数据契约。
<!-- aeps-llm-wiki-plugin:end -->`;

const CONTROLLED_RE = /<!-- aeps-llm-wiki-plugin:start -->[\s\S]*?<!-- aeps-llm-wiki-plugin:end -->/;
const LEGACY_RE = /<!-- aeps-llm-wiki-plugin:start -->[\s\S]*?<!-- aeps-llm-wiki-plugin:end -->/;  // same regex for legacy detection — strict

function parseArgs(argv) {
  const args = { project: null, dryRun: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--dry-run') args.dryRun = true;
  }
  if (!args.project) {
    console.error('Error: --project <dir> is required');
    process.exit(1);
  }
  return args;
}

async function exists(p) {
  try { await fs.access(p); return true; } catch { return false; }
}

async function patch(args) {
  const project = path.resolve(args.project);
  const filePath = path.join(project, 'CLAUDE.md');
  const dryRun = args.dryRun;

  const result = { project, filePath, action: 'skipped', dryRun };

  if (!(await exists(filePath))) {
    // create
    const content = CONTROLLED_BLOCK + '\n';
    if (!dryRun) await fs.writeFile(filePath, content, 'utf8');
    result.action = 'created';
    return result;
  }

  const original = await fs.readFile(filePath, 'utf8');

  // Try strict regex match
  if (CONTROLLED_RE.test(original)) {
    // ponytail: extract matched block and compare to canonical
    const match = original.match(CONTROLLED_RE);
    const matchedBlock = match[0];
    if (matchedBlock === CONTROLLED_BLOCK) {
      result.action = 'skipped';  // already canonical
      return result;
    }
    // differs → replace in place
    const replaced = original.replace(CONTROLLED_RE, CONTROLLED_BLOCK);
    if (!dryRun) await fs.writeFile(filePath, replaced, 'utf8');
    result.action = 'updated';
    return result;
  }

  // No canonical marker. Check for any user-edited start/end markers (orphan markers).
  // ponytail: per implement-init.md §6.1 "匹配失败 → 报错退出,不静默追加"
  const orphanStart = /<!-- aeps-llm-wiki-plugin:start -->/.test(original);
  const orphanEnd = /<!-- aeps-llm-wiki-plugin:end -->/.test(original);
  if (orphanStart || orphanEnd) {
    // User has orphan markers — strict mode: refuse to silently overwrite.
    result.action = 'error';
    result.error = 'orphan_markers_detected';
    result.message = 'CLAUDE.md contains orphan aeps-llm-wiki-plugin markers. Please remove or fix them manually before re-running init.';
    return result;
  }

  // No markers at all → append canonical block to end
  // ponytail: ensure trailing newline before append
  const sep = original.endsWith('\n') ? '\n' : '\n\n';
  const appended = original + sep + CONTROLLED_BLOCK + '\n';
  if (!dryRun) await fs.writeFile(filePath, appended, 'utf8');
  result.action = 'appended';
  return result;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = await patch(args);
  console.log(JSON.stringify(result, null, 2));
  // ponytail: exit 0 on error action too — SKILL.md reads action field; non-zero only on argv errors
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(3);
});
