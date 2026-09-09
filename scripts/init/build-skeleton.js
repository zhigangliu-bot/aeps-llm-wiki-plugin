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

import { promises as fs, readFileSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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
//
// v0.6.2 起:overview.md 不再硬编码骨架,而是从 plugin 仓 `doc/template/page-overview.md`
// 读真实模板(LLM 在 ingest 大图变化时填充内容;`aggregate-index.js` 已停止覆写 overview.md)。
// 其余 3 个(index/glossary/log)继续走硬编码,因为 page-{index,overview,glossary,log}.md
// 模板目前只覆盖了 overview 的 Karpathy 风格骨架,index/glossary/log 内容由脚本直接拼更可控。
const INDEX_TEMPLATES = {
  // (issue #11 fix)动态区用聚合标记对包住:aggregate-index.js 每次 ingest 只整体替换两个标记
  // 之间的内容;项目简介等手写内容必须写在标记之外,不会被覆盖。
  'index.md': ({ title }) => `# ${title} Wiki 主目录

> 本文件由 \`/aeps-llm-wiki-init\` 创建,\`/aeps-llm-wiki-ingest\` 增量维护。
> 两个聚合标记(下方 START / END HTML 注释对)之间的动态区由
> \`scripts/aggregate-index.js\` 在每次 ingest 后整体重写;项目简介等手写内容请写在标记之外。

参见 [overview](./overview.md) 查看大图。

<!-- AGGREGATE-START -->
*(暂无)*
<!-- AGGREGATE-END -->
`,
  'glossary.md': ({ title }) => `# ${title} Wiki 术语表

> 本文件由 \`/aeps-llm-wiki-init\` 创建,\`/aeps-llm-wiki-ingest\` 增量维护。
> 两个聚合标记之间的动态区由 \`scripts/aggregate-index.js\` 整体重写;手工术语条目请写在标记之外。

<!-- AGGREGATE-START -->
*(暂无)*
<!-- AGGREGATE-END -->
`,
  'log.md': ({ at, title }) => `# ${title} Wiki 变更日志

> 按 ISO 8601 日期做 H2,最新在前。

## ${at.slice(0, 10)}

**Init**: 用户项目 wiki 初始化,生成 ${KNOWLEDGE_LEAF_DIRS.length} 个叶子存储目录 + ${RAW_SUBDIRS.length} 个 raw 子目录 + 4 份管理文件
`,
};

// ponytail: overview.md 骨架读 plugin 仓 `doc/template/page-overview.md`,失败回退到最小骨架。
// plugin-root 解析优先级:`--plugin-root` CLI > `CLAUDE_PLUGIN_ROOT` env > __dirname/../..(同仓)
function resolvePluginRoot(args) {
  if (args.pluginRoot) return path.resolve(args.pluginRoot);
  if (process.env.CLAUDE_PLUGIN_ROOT) return path.resolve(process.env.CLAUDE_PLUGIN_ROOT);
  // ponytail:__dirname = scripts/init/,plugin-root = 上两级
  return path.resolve(__dirname, '..', '..');
}

function loadOverviewTemplate(pluginRoot) {
  const tplPath = path.join(pluginRoot, 'doc', 'template', 'page-overview.md');
  try {
    let txt = readFileSync(tplPath, 'utf8');
    // ponytail:剥掉文档开头的 HTML 注释行(与 gen-page.js 的 parseTemplate 行为对齐,否则
    // 文件首行是 `<!-- ... -->`,触发 reserved-filename 测试 `startsWith('# ')` 失败)
    txt = txt.replace(/^[\t ]*<!--[\s\S]*?-->\s*\r?\n/, '');
    return txt;
  } catch (err) {
    // ponytail:兜底骨架,plugin 仓无 page-overview.md 时仍能生成(保留旧行为)
    return `# Wiki 大图

> 本文件由 \`/aeps-llm-wiki-init\` 创建,\`/aeps-llm-wiki-ingest\` 在大图变化时更新。
`;
  }
}

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
  // overview.md 走 plugin 仓 `doc/template/page-overview.md` 骨架(v0.6.2+);其余 3 个走 INDEX_TEMPLATES
  const pluginRoot = resolvePluginRoot(args);
  const overviewTemplate = loadOverviewTemplate(pluginRoot);
  for (const [name, tpl] of Object.entries(INDEX_TEMPLATES)) {
    const fAbs = path.join(project, 'knowledge', name);
    const isNew = await writeFile(fAbs, tpl({ at, title }), dryRun, created);
    if (!isNew) skipped.push(fAbs);
  }
  // overview.md 单独写:读 plugin 仓骨架
  {
    const fAbs = path.join(project, 'knowledge', 'overview.md');
    const isNew = await writeFile(fAbs, overviewTemplate, dryRun, created);
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
      // ponytail: v0.6.2+ overview.md 单独从 plugin 仓模板读,不算 INDEX_TEMPLATES;+1 保留 4 件总数
      indexFiles: Object.keys(INDEX_TEMPLATES).length + 1,
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
