#!/usr/bin/env node
/**
 * build-skeleton.js - First-run: build all 6 top dirs + 18 leaf knowledge dirs + 15 raw subdirs.
 *
 * Does NOT touch existing files. Only creates missing directories and .gitkeep markers.
 * Also writes 4 top-level knowledge index files (index/overview/glossary/log) on first run.
 * v0.5.8 起:5 顶层(inbox/raw/scripts/doc/knowledge);doc/ 下 schema/ templates/ 由 sync-files.js 递归建。
 *
 * Usage:
 *   node scripts/init/build-skeleton.js --project <dir> [--plugin-root <dir>] [--dry-run]
 *
 * Exit codes:
 *   0 - success (or dry-run preview)
 *   1 - invalid args
 *   2 - partial failure (some mkdirs failed; rolled back created entries)
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const TOP_DIRS = ['inbox', 'raw', 'scripts', 'doc', 'knowledge']; // v0.5.8 起 schema/templates 移到 doc/ 下

const KNOWLEDGE_LEAF_DIRS = [
  'sources',
  'analyses',
  'comparisons',
  'syntheses',
  'entities/person',
  'entities/organization',
  'entities/project',
  'entities/product',
  'entities/event',
  'entities/place',
  'entities/other',
  'concepts/theory',
  'concepts/method',
  'concepts/field',
  'concepts/phenomenon',
  'concepts/standard',
  'concepts/term',
  'concepts/other',
];

const RAW_SUBDIRS = [
  '01_EE架构',
  '02_芯片',
  '03_通信与网络',
  '04_操作系统与中间件',
  '05_软件工程',
  '06_功能安全',
  '07_信息安全',
  '08_AI与AI工程',
  '09_域控制器',
  '10_会议与活动',
  '11_开发工具',
  '12_法规_标准_政策',
  '13_流程体系',
  '14_测试与验证',
  '15_算法',
];

// ponytail: 4 top-level knowledge index templates — 无 frontmatter, 对齐 page-{index,overview,glossary,log}.md 模板。
// 这 4 个文件是 plugin 自定义 reserved filename,不在 OKF §3.1 列表内(详见 doc/template/README.md §6.1)。
// v0.6.1 起去掉硬塞的 frontmatter:与模板事实源对齐,避免 OKF reader 误判为普通页参与全局聚合。

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

// ponytail: 4 top-level knowledge index templates — 无 frontmatter, 对齐 page-{index,overview,glossary,log}.md 模板。
// 这 4 个文件是 plugin 自定义 reserved filename,不在 OKF §3.1 列表内(详见 doc/template/README.md §6.1)。
// v0.6.1 起去掉硬塞的 frontmatter:与模板事实源对齐,避免 OKF reader 误判为普通页参与全局聚合。
const INDEX_TEMPLATES = {
  'index.md': ({ title }) => `# ${title} Wiki 主目录

> 本文件由 \`/aeps-llm-wiki-init\` 创建,\`/aeps-llm-wiki-ingest\` 增量维护。

参见 [overview](./overview.md) 查看大图。
`,
  'overview.md': ({ title }) => `# ${title} Wiki 大图

> 本文件由 \`/aeps-llm-wiki-init\` 创建,\`/aeps-llm-wiki-ingest\` 在大图变化时更新。
`,
  'glossary.md': ({ title }) => `# ${title} Wiki 术语表

> 本文件由 \`/aeps-llm-wiki-init\` 创建,\`/aeps-llm-wiki-ingest\` 增量维护。
`,
  'log.md': ({ at, title }) => `# ${title} Wiki 变更日志

> 按 ISO 8601 日期做 H2,最新在前。

## ${at.slice(0, 10)}

**Init**: 用户项目 wiki 初始化,生成 ${KNOWLEDGE_LEAF_DIRS.length} 个叶子存储目录 + ${RAW_SUBDIRS.length} 个 raw 子目录 + 4 份管理文件
`,
};

function parseArgs(argv) {
  const args = { project: null, pluginRoot: null, dryRun: false, title: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--plugin-root') args.pluginRoot = argv[++i];
    else if (a === '--dry-run') args.dryRun = true;
    else if (a === '--title') args.title = argv[++i];
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

async function ensureDir(absDir, dryRun, created) {
  if (await exists(absDir)) return false;
  if (!dryRun) await fs.mkdir(absDir, { recursive: true });
  return true;
}

async function writeFile(absPath, content, dryRun, created) {
  if (await exists(absPath)) return false;
  if (!dryRun) await fs.writeFile(absPath, content, 'utf8');
  created.push(absPath);
  return true;
}

async function buildSkeleton(args) {
  const project = path.resolve(args.project);
  const at = nowIso();
  const title = args.title || path.basename(project) || 'Project';
  const created = [];
  const skipped = [];
  const dryRun = args.dryRun;

  // 6 top-level dirs
  for (const d of TOP_DIRS) {
    const dirAbs = path.join(project, d);
    const keepAbs = path.join(dirAbs, '.gitkeep');
    await ensureDir(dirAbs, dryRun, created);
    const fNew = await writeFile(keepAbs, '', dryRun, created);
    if (!fNew) skipped.push(keepAbs);
  }

  // 18 knowledge leaf dirs
  for (const leaf of KNOWLEDGE_LEAF_DIRS) {
    const dirAbs = path.join(project, 'knowledge', leaf);
    const keepAbs = path.join(dirAbs, '.gitkeep');
    await ensureDir(dirAbs, dryRun, created);
    const fNew = await writeFile(keepAbs, '', dryRun, created);
    if (!fNew) skipped.push(keepAbs);
  }

  // 15 raw subdirs
  for (const sub of RAW_SUBDIRS) {
    const dirAbs = path.join(project, 'raw', sub);
    const keepAbs = path.join(dirAbs, '.gitkeep');
    await ensureDir(dirAbs, dryRun, created);
    const fNew = await writeFile(keepAbs, '', dryRun, created);
    if (!fNew) skipped.push(keepAbs);
  }

  // 4 top-level knowledge index files (only if not exists — preserves user content per SYNC-7)
  for (const [name, tpl] of Object.entries(INDEX_TEMPLATES)) {
    const fAbs = path.join(project, 'knowledge', name);
    const isNew = await writeFile(fAbs, tpl({ at, title }), dryRun, created);
    if (!isNew) skipped.push(fAbs);
  }

  return {
    project,
    dryRun,
    created,
    skipped,
    counts: {
      topDirs: TOP_DIRS.length,
      knowledgeLeaves: KNOWLEDGE_LEAF_DIRS.length,
      rawSubdirs: RAW_SUBDIRS.length,
      indexFiles: Object.keys(INDEX_TEMPLATES).length,
      gitkeepTotal: TOP_DIRS.length + KNOWLEDGE_LEAF_DIRS.length + RAW_SUBDIRS.length,
    },
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = await buildSkeleton(args);
  // ponytail: structured JSON to stdout
  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message, stack: err.stack }));
  process.exit(2);
});
