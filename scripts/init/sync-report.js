#!/usr/bin/env node
/**
 * sync-report.js - Aggregate sync results from prior init phase into a human-readable summary.
 *
 * Reads JSON output of build-skeleton / sync-files / patch-claude-md via stdin
 * (one JSON per line) and produces a single summary.
 *
 * Usage:
 *   node scripts/init/sync-report.js --project <dir> [--json]
 *   # OR pipe JSON lines via stdin:
 *   cat results.jsonl | node scripts/init/sync-report.js --project <dir>
 *
 * JSON output(P2-4 批次 3 修复):
 *   主输出从"本次变更数"改为"本次后工程根实际状态(state_snapshot)",便于幂等再跑时直观看到。
 *   - project_root: <abs>
 *   - state_snapshot:
 *       - gitkeep_count: 工程根所有 .gitkeep 数(对齐 6+18+15=39)
 *       - knowledge_pages: knowledge/ 下 .md 页数(不含 index/overview/glossary/log)
 *       - raw_subdirs: raw/ 子目录数(对齐 15)
 *       - index_files: 顶层索引文件数(index.md / overview.md / glossary.md / log.md 等)
 *   - delta_from_last_run: { added, updated, skipped, warned } (从 stdin JSON lines 聚合,向后兼容)
 *
 * Exit codes: 0 ok / 1 参数错 / 2 缺依赖
 *
 * change history:
 *   - 0.5.6: P2-4 state_snapshot 主输出改为工程根实际状态(批次 3)
 *   - 0.5.6: inline preflight(批次 3)
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { requireDeps } from '../lib/preflight.js';
// sync-report.js 不依赖 js-yaml/ajv(只读 stdin JSON)
await requireDeps({});

function parseArgs(argv) {
  const args = { project: null, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--json') args.json = true;
  }
  if (!args.project) {
    console.error('Error: --project <dir> is required');
    process.exit(1);
  }
  return args;
}

async function readStdin() {
  // ponytail: read all stdin (assumed small — sync outputs only)
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

/**
 * 扫描工程根目录的当前状态(P2-4 批次 3)
 * 返回:
 *   - gitkeep_count: 工程根 .gitkeep 文件数(对齐 6+18+15=39)
 *   - knowledge_pages: knowledge/ 下 .md 页数(不含 index/overview/glossary/log)
 *   - raw_subdirs: raw/ 子目录数(对齐 15)
 *   - index_files: 顶层索引文件数(index.md / overview.md / glossary.md / log.md)
 */
async function scanStateSnapshot(project) {
  async function walkGitkeep(dir, depth) {
    if (depth > 3) return 0;
    let entries;
    try { entries = await fs.readdir(dir, { withFileTypes: true }); } catch { return 0; }
    let n = 0;
    for (const e of entries) {
      // 跳过隐藏目录(.git 等),但不过滤 .gitkeep 文件
      if (e.name.startsWith('.') && e.isDirectory()) continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) n += await walkGitkeep(full, depth + 1);
      else if (e.isFile() && e.name === '.gitkeep') n++;
    }
    return n;
  }

  async function countKnowledgePages(project) {
    const knowledgeDir = path.join(project, 'knowledge');
    let count = 0;
    async function walk(dir) {
      let entries;
      try { entries = await fs.readdir(dir, { withFileTypes: true }); } catch { return; }
      for (const e of entries) {
        if (e.name.startsWith('.')) continue;
        const full = path.join(dir, e.name);
        if (e.isDirectory()) await walk(full);
        else if (e.isFile() && e.name.endsWith('.md')) count++;
      }
    }
    await walk(knowledgeDir);
    return count;
  }

  async function countRawSubdirs(project) {
    const rawDir = path.join(project, 'raw');
    try {
      const entries = await fs.readdir(rawDir, { withFileTypes: true });
      return entries.filter(e => e.isDirectory() && !e.name.startsWith('.')).length;
    } catch { return 0; }
  }

  // 顶层索引文件(index.md / overview.md / glossary.md / log.md)
  async function countIndexFiles(project) {
    let n = 0;
    for (const name of ['index.md', 'overview.md', 'glossary.md', 'log.md']) {
      try { await fs.access(path.join(project, 'knowledge', name)); n++; } catch { /* skip */ }
    }
    return n;
  }

  const [gitkeep_count, knowledge_pages, raw_subdirs, index_files] = await Promise.all([
    walkGitkeep(project, 0),
    countKnowledgePages(project),
    countRawSubdirs(project),
    countIndexFiles(project),
  ]);

  return { gitkeep_count, knowledge_pages, raw_subdirs, index_files };
}

async function report(args) {
  const project = path.resolve(args.project);
  const stdinData = await readStdin().catch(() => '');
  const lines = stdinData.split(/\r?\n/).filter(Boolean);
  const phases = [];
  for (const line of lines) {
    try {
      phases.push(JSON.parse(line));
    } catch {
      // ignore non-JSON lines
    }
  }

  // ponytail: aggregate counts across phases
  let addedCount = 0, updatedCount = 0, skippedCount = 0, warnedCount = 0;
  const allAdded = [];
  const allUpdated = [];
  const allSkipped = [];
  const allWarned = [];
  for (const p of phases) {
    if (Array.isArray(p.added)) { allAdded.push(...p.added); addedCount += p.added.length; }
    if (Array.isArray(p.updated)) { allUpdated.push(...p.updated); updatedCount += p.updated.length; }
    if (Array.isArray(p.skipped)) { allSkipped.push(...p.skipped); skippedCount += p.skipped.length; }
    if (Array.isArray(p.warned)) { allWarned.push(...p.warned); warnedCount += p.warned.length; }
  }

  // P2-4 批次 3: 扫描工程根实际状态(主输出)
  const state_snapshot = await scanStateSnapshot(project);

  const summary = {
    project: project.replace(/\\/g, '/'),
    state_snapshot,
    delta_from_last_run: { added: addedCount, updated: updatedCount, skipped: skippedCount, warned: warnedCount },
    phases: phases.length,
    counts: { added: addedCount, updated: updatedCount, skipped: skippedCount, warned: warnedCount },
    added: allAdded,
    updated: allUpdated,
    skipped: allSkipped,
    warned: allWarned,
    status: 'init_complete',
  };

  if (args.json) {
    console.log(JSON.stringify(summary, null, 2));
    return;
  }

  // ponytail: human-readable report
  const lines2 = [];
  lines2.push('=== init sync summary ===');
  lines2.push(`project: ${project}`);
  lines2.push(`phases: ${phases.length}`);
  lines2.push('--- 工程根当前状态(state_snapshot) ---');
  lines2.push(`  gitkeep_count:    ${state_snapshot.gitkeep_count}`);
  lines2.push(`  knowledge_pages:  ${state_snapshot.knowledge_pages}`);
  lines2.push(`  raw_subdirs:      ${state_snapshot.raw_subdirs}`);
  lines2.push(`  index_files:      ${state_snapshot.index_files}`);
  lines2.push('--- 本次变更(delta_from_last_run) ---');
  lines2.push(`  added:   ${addedCount}`);
  lines2.push(`  updated: ${updatedCount}`);
  lines2.push(`  skipped: ${skippedCount}`);
  lines2.push(`  warned:  ${warnedCount}`);
  if (allAdded.length) {
    lines2.push('\n--- added files ---');
    for (const f of allAdded) lines2.push('+ ' + f);
  }
  if (allUpdated.length) {
    lines2.push('\n--- updated files ---');
    for (const f of allUpdated) lines2.push('~ ' + f);
  }
  if (allSkipped.length > 0 && allSkipped.length <= 50) {
    lines2.push('\n--- skipped (preserved) ---');
    for (const f of allSkipped) lines2.push('  ' + f);
  } else if (allSkipped.length > 50) {
    lines2.push(`\n--- skipped (${allSkipped.length} total, omitted for brevity) ---`);
  }
  if (allWarned.length) {
    lines2.push('\n--- warnings ---');
    for (const w of allWarned) lines2.push('! ' + w);
  }
  lines2.push('\n=== init complete ===');
  console.log(lines2.join('\n'));
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  await report(args);
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(1);
});
