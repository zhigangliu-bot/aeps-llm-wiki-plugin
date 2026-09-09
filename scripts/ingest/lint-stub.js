#!/usr/bin/env node
/**
 * lint-stub.js — M2.4 lint skill 预留 stub(M2.4 落地前的临时实现)
 *
 * 本脚本是 lint skill (M2.4 任务) 的接口占位。
 * v0.5.6 起(批次 3 修复 P2-5):本 stub 不再固定 fail=0/warn=0,落地两条最小规则:
 *   - R7.1 (WARN): 扫所有 knowledge 目录 .md 页 frontmatter tags 字段长度,<5 时 WARN
 *   - R7.2 (ERROR): 扫所有知识页 frontmatter `updated` 字段是否符合 ISO 8601,不符合时 ERROR
 * v0.5.9 起:加一条 v0.5.9 强约束
 *   - C21 (WARN): source 页 `## 重点摘录` 之前缺自由追加节 → WARN
 *                (对齐 page-source.md v0.5.9 起占位骨架 ## 阅读路线)
 *
 * SKILL.md 步骤 19 调 `node scripts/ingest/lint-stub.js --project <dir>` 解析输出。
 *
 * 接口契约(锁定):
 *   - 输入:--project <dir>  (必填)
 *   - 输出(stdout): JSON 形如:
 *       {
 *         "project": "<dir>",
 *         "linted":  <number>,     // 扫到的 knowledge/ 页数
 *         "fail":    <number>,     // R7.2 ISO 8601 失败数 + 旧 stub 永远 0
 *         "warn":    <number>,     // R7.1 tags <5 数 + 旧 stub 永远 0
 *         "stub":    true,
 *         "lint_version": "M2.4-stub",
 *         "scanned_at": "<ISO 8601>",
 *         "warnings_by_file": {     // P2-1 复用,与 build-related-pages.js 字段对齐
 *           "knowledge/...": ["tags 仅 4 条,需 ≥5 条", "..."]
 *         },
 *         "errors_by_file": {       // R7.2 新增
 *           "knowledge/...": ["updated 字段不符合 ISO 8601: <value>"]
 *         }
 *       }
 *   - Exit code:
 *       0 - 成功(无 fail)
 *       1 - 参数错
 *       2 - 有 fail(规则 R7.2 触发)或缺依赖
 *
 * 设计原则:
 *   - **不动 lint 真实实现**:M2.4 任务会替换本 stub 内容,但接口契约(stdin/stdout/exit)不变。
 *   - **不破坏 SKILL.md 步骤 19 编排**:本 stub 输出 JSON 含 `linted` / `fail` / `warn` 字段,SKILL.md
 *     可正常解析;后续 M2.4 实现只需保证字段含义一致。
 *   - **不引入新依赖**:仅用 node:fs / node:path / node:process / scripts/lib/*(iso8601 复用)。
 *
 * change history:
 *   - 0.5.9: 加 C21(source 页 ## 重点摘录 之前缺自由追加节 WARN);scanKnowledgePages 同步带 body
 *   - 0.5.6: P2-5 真做两条规则(tags<5 WARN + updated ISO 8601 ERROR)(批次 3)
 *   - 0.5.6: inline preflight(批次 3)
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { requireDeps } from '../lib/preflight.js';
import { isIso8601 } from '../lib/iso8601.js';
// 批次 3 P1-6: inline preflight 先跑;缺包 → throw 含精确 npm install 命令
await requireDeps({ 'js-yaml': 'js-yaml' });
// 动态 import:必须在 requireDeps 之后
const yaml = (await import('js-yaml')).default;

const STUB_VERSION = 'M2.4-stub';
const MIN_TAGS_LENGTH = 5; // 对齐 doc/schema/frontmatter.schema.json tags minItems
// v0.5.9: C21 — source 页 ## 重点摘录 之前缺自由追加节 WARN
// (page-source.md v0.5.9 起把"自由追加节"从注释软指引升级为占位骨架 ## 阅读路线,
//  强制 LLM 读完源文件后先问『这篇有什么独特结构』再写正文)
const REQUIRED_BEFORE_KEY = '## 重点摘录';

function parseFrontmatter(mdText) {
  const m = mdText.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  if (!m) return { fm: {}, body: mdText };
  let fm = {};
  try { fm = yaml.load(m[1]) || {}; } catch { fm = {}; }
  return { fm, body: m[2] };
}

/**
 * 返回 body 中所有 H2 节标题(去掉开头的 ## 与尾部空白)。
 * 用于 C21: 校验 source 页 ## 重点摘录 之前的 H2 自由追加节是否齐全。
 * 注: 同一节里嵌套的 ###/#### 不计入。
 */
function listH2Sections(body) {
  const out = [];
  const lines = body.split(/\r?\n/);
  for (const line of lines) {
    const m = line.match(/^##\s+(.+?)\s*$/);
    if (m) out.push(m[1]);
  }
  return out;
}

/**
 * 扫 <project>/knowledge/ 下所有 .md 页(排除 .gitkeep / 隐藏文件)。
 * 返回 [{ relPath, fm }] 列表。
 */
async function scanKnowledgePages(project) {
  const knowledgeDir = path.join(project, 'knowledge');
  const out = [];
  async function walk(dir, relBase) {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return; // knowledge/ 不存在 → 空
    }
    for (const e of entries) {
      if (e.name.startsWith('.')) continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        await walk(full, relBase ? `${relBase}/${e.name}` : e.name);
      } else if (e.isFile() && e.name.endsWith('.md')) {
        const txt = await fs.readFile(full, 'utf8');
        const { fm, body } = parseFrontmatter(txt);
        const relPath = relBase ? `${relBase}/${e.name}` : e.name;
        out.push({ relPath: `knowledge/${relPath}`.replace(/\\/g, '/'), fm, body });
      }
    }
  }
  await walk(knowledgeDir, '');
  return out;
}

function parseArgs(argv) {
  const args = { project: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
  }
  if (!args.project) {
    console.error('ERROR: --project <dir> 必填');
    process.exit(1);
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const project = path.resolve(args.project);
  const pages = await scanKnowledgePages(project);

  const warningsByFile = {};
  const errorsByFile = {};
  const flatWarnings = [];
  const flatErrors = [];

  for (const p of pages) {
    const tags = Array.isArray(p.fm.tags) ? p.fm.tags : [];
    const updated = p.fm.updated;

    // R7.1: tags.length < 5 → WARN
    if (tags.length < MIN_TAGS_LENGTH) {
      const msg = `tags 仅 ${tags.length} 条,需 ≥${MIN_TAGS_LENGTH} 条`;
      if (!warningsByFile[p.relPath]) warningsByFile[p.relPath] = [];
      warningsByFile[p.relPath].push(msg);
      flatWarnings.push(`${p.relPath}: ${msg}`);
    }

    // R7.2: updated 不符合 ISO 8601 → ERROR(updated 字段不存在也算 ERROR)
    if (!updated || !isIso8601(updated)) {
      const msg = `updated 字段不符合 ISO 8601: ${updated === undefined || updated === null ? '(missing)' : String(updated)}`;
      if (!errorsByFile[p.relPath]) errorsByFile[p.relPath] = [];
      errorsByFile[p.relPath].push(msg);
      flatErrors.push(`${p.relPath}: ${msg}`);
    }

    // C21 (v0.5.9): source 页 ## 重点摘录 之前缺自由追加节 → WARN
    // 只对 type: source 触发(其它类型如 analysis / entity.* 等不锁 H2 骨架,不参与 C21)
    if (p.fm.type === 'source') {
      const h2s = listH2Sections(p.body || '');
      const idxKey = h2s.indexOf('重点摘录');
      const hasFreeSection = idxKey > 0;
      if (idxKey !== -1 && !hasFreeSection) {
        const msg = `source 页 ## 重点摘录 之前缺自由追加节(占位骨架 ## 阅读路线,必填或改名为本文具体节名)`;
        if (!warningsByFile[p.relPath]) warningsByFile[p.relPath] = [];
        warningsByFile[p.relPath].push(msg);
        flatWarnings.push(`${p.relPath}: ${msg}`);
      }
    }
  }

  const out = {
    project: project.replace(/\\/g, '/'),
    linted: pages.length,
    fail: flatErrors.length,
    warn: flatWarnings.length,
    stub: true,
    lint_version: STUB_VERSION,
    scanned_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    warnings_by_file: warningsByFile,
    errors_by_file: errorsByFile,
    warnings: flatWarnings,
    errors: flatErrors,
  };
  console.log(JSON.stringify(out, null, 2));
  // 有 fail → exit 2(对齐 SKILL.md 步骤 19:"FAIL 必须修复后才算 ingest 完成")
  process.exit(out.fail > 0 ? 2 : 0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(2);
});
