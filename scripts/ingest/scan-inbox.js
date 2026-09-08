#!/usr/bin/env node
/**
 * scan-inbox.js — 递归扫 inbox/ 过滤 .gitkeep/.DS_Store/README.md/隐藏文件
 *
 * Usage:
 *   node scripts/ingest/scan-inbox.js --inbox <dir> [--json]
 *
 * Exit codes:
 *   0 - 成功
 *   1 - 参数错
 *   2 - inbox 目录不存在
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { requireDeps } from '../lib/preflight.js';
await requireDeps({});

const IGNORED_NAMES = new Set(['.gitkeep', '.DS_Store', 'README.md', 'Thumbs.db']);
const IGNORED_PREFIX = '.'; // 隐藏文件

async function exists(p) {
  try { await fs.access(p); return true; } catch { return false; }
}

async function walk(absDir) {
  const out = [];
  let entries;
  try {
    entries = await fs.readdir(absDir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const e of entries) {
    const full = path.join(absDir, e.name);
    // 过滤隐藏文件 + 元数据 + README
    if (IGNORED_PREFIX === e.name[0]) continue;
    if (IGNORED_NAMES.has(e.name)) continue;
    if (e.isDirectory()) {
      const sub = await walk(full);
      out.push(...sub);
    } else if (e.isFile()) {
      const stat = await fs.stat(full);
      const ext = path.extname(e.name).toLowerCase().replace(/^\./, '');
      // 路径用 POSIX 正斜杠(Obsidian / frontmatter wikilink 兼容)
      out.push({
        path: full.replace(/\\/g, '/'),
        size: stat.size,
        ext,
        mtime: new Date(stat.mtimeMs).toISOString().replace(/\.\d{3}Z$/, 'Z'),
      });
    }
  }
  return out;
}

function parseArgs(argv) {
  const args = { inbox: null, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--inbox') args.inbox = argv[++i];
    else if (a === '--json') args.json = true;
  }
  if (!args.inbox) {
    console.error('ERROR: --inbox <dir> is required');
    process.exit(1);
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const inbox = path.resolve(args.inbox);
  if (!(await exists(inbox))) {
    console.error(`ERROR: inbox 目录不存在: ${inbox}`);
    process.exit(2);
  }
  const files = await walk(inbox);
  const result = {
    inbox: inbox.replace(/\\/g, '/'),
    files,
    count: files.length,
    scanned_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
  };
  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(2);
});
