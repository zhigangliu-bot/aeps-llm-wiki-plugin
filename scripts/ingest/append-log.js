#!/usr/bin/env node
/**
 * append-log.js — 追加 **Ingest:** 到 knowledge/log.md
 *
 * Usage:
 *   node scripts/ingest/append-log.js --project <dir> --batch <batch.json> [--apply] [--json]
 *
 * 行为:
 *   - 读 batch.json files[]
 *   - 追加格式:
 *     `**Ingest**: inbox/<file> → raw/<subdir>/<file> (+ converted.md);新建 <list>`
 *   - 到 knowledge/log.md 对应 ISO 8601 日期 H2 下(YYYY-MM-DD)
 *   - 已有当天 H2 → 复用;无 → 插入新 H2 (最新在前,按 Q5)
 *   - 不动已有 Init/Creation/LintFix 等条目
 *
 * JSON output 增加 `entries` 数组(P1-4 批次 3 修复):
 *   - 每个元素 { file, action, summary }
 *   - action ∈ { added, merged, skipped }
 *     - added:    本批次新增条目(当天 H2 新建)
 *     - merged:   本批次追加到当天 H2(已有当天,合并)
 *     - skipped:  批次内某文件已处理过(dedupe_key 已存在)
 *
 * Exit codes:
 *   0 - 成功
 *   1 - 参数错
 *   2 - 写盘失败 / 缺依赖
 *
 * change history:
 *   - 0.6.x:**Ingest** 行 `新建 [[slug]]` 改为纯文本 `新建 slug`(log.md 不进知识图谱,
 *     wikilink 会让 graph view 渲染混乱;对齐 page-log.md 模板示例,其本就无 wikilink)
 *   - 0.6.6 (issue #30 fix, PR-C):**Ingest** 行追加 entity / concept 抽取结果
 *     (从 `batch.files[].entities[]` / `batch.files[].concepts[]` 读,元素 schema
 *     `{type, slug, title?}` 与 build-related-pages.js:697-700 对齐);
 *     log 行格式变为:
 *       `**Ingest**: inbox/<basename> → raw/<subdir>/<target>;新建 [[slug]] + entities/<dir>/<slug>.md + concepts/<dir>/<slug>.md`
 *     知识图谱变化追溯完整(不再残缺);与 doc/template/page-log.md 模板示例对齐,
 *     修正 SKILL.md 步骤 17 / 模板 / 实现三方的契约漂移。
 *   - 0.5.6: P1-4 entries 数组(批次 3)
 *   - 0.5.6: inline preflight(批次 3)
 *   - 0.6.0: P1-#4 (issue #4) — wikilink 优先用 file.slug 而非 path basename:
 *     旧版用 inbox 原文件名 basename → slug 重命名后 wikilink 指向不存在文件
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { requireDeps } from '../lib/preflight.js';
// 批次 3 P1-6: inline preflight 先跑;缺包 → throw 含精确 npm install 命令
await requireDeps({ 'js-yaml': 'js-yaml' });
// 动态 import:必须在 requireDeps 之后
const yaml = (await import('js-yaml')).default;

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function todayDate(iso) {
  return iso.slice(0, 10); // YYYY-MM-DD
}

async function readJson(p) {
  const txt = await fs.readFile(p, 'utf8');
  return JSON.parse(txt);
}

function parseFrontmatter(mdText) {
  const m = mdText.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  if (!m) return { fm: null, body: mdText };
  let fm = null;
  try { fm = yaml.load(m[1]) || null; } catch { fm = null; }
  return { fm, body: m[2] };
}

function renderFrontmatterBlock(fm) {
  return '---\n' + yaml.dump(fm, { lineWidth: -1, quotingType: '"', forceQuotes: false }) + '---\n';
}

function parseArgs(argv) {
  const args = { project: null, batch: null, apply: false, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--batch') args.batch = argv[++i];
    else if (a === '--apply') args.apply = true;
    else if (a === '--json') args.json = true;
  }
  if (!args.project || !args.batch) {
    console.error('ERROR: --project / --batch 必填');
    process.exit(1);
  }
  return args;
}

/**
 * 解析 log.md body 成 [{date, content}] 列表
 * 每个 H2 ## [YYYY-MM-DD] 占一段(v0.5.6 起:对齐 Karpathy LLM Wiki log.md,加方括号视觉区分)
 * 自动剥离节末尾的 `---` 水平线(对齐 page-log.md 模板)与文末 `## 维护` 节,保证 round-trip 幂等
 */
function parseLogSections(body) {
  const lines = body.split('\n');
  // 1. 切掉文末 `## 维护` 节(由 renderLogSections 末尾追加,parse 时不应吸收)
  const cutoff = lines.findIndex((l, i) => l.trim() === '## 维护');
  const core = cutoff >= 0 ? lines.slice(0, cutoff) : lines;

  // 2. 按 ## [YYYY-MM-DD] H2 切片(v0.5.6 起加方括号)
  const sections = [];
  let cur = null;
  for (const line of core) {
    const m = line.match(/^##\s+\[(\d{4}-\d{2}-\d{2})\]\s*$/);
    if (m) {
      if (cur) sections.push(cur);
      cur = { date: m[1], content: [] };
    } else if (cur) {
      cur.content.push(line);
    } else {
      // 文件开头可能有些 H1/前言;忽略
    }
  }
  if (cur) sections.push(cur);

  // 3. 每节内容 trimEnd + 剥离节末尾连续的 `---` 水平线
  for (const s of sections) {
    while (s.content.length && s.content[s.content.length - 1].trim() === '') {
      s.content.pop();
    }
    if (s.content.length && s.content[s.content.length - 1].trim() === '---') {
      s.content.pop();
    }
    while (s.content.length && s.content[s.content.length - 1].trim() === '') {
      s.content.pop();
    }
  }
  return sections;
}

/**
 * 把 sections 拼回 body(对齐 doc/template/page-log.md,v0.5.6 起输出 ## [YYYY-MM-DD])
 * 每个日期节末尾追加 `---` 水平线
 * 文末追加 `## 维护` 节(若不存在)
 */
function renderLogSections(sections) {
  if (!sections.length) return '';
  const out = [];
  for (const s of sections) {
    out.push(`## [${s.date}]`);
    out.push('');
    out.push(...s.content);
    out.push('');
    out.push('---');
  }
  // 文末 ## 维护 节(对齐模板)
  out.push('');
  out.push('## 维护');
  out.push('');
  out.push('- 字段定义权威:`../doc/schema/frontmatter-spec.md`(人读规范,唯一权威);`../doc/schema/frontmatter.schema.json` 跟随对齐');
  out.push('- 本文件由 SKILL.md 在每次 ingest / query 落档 / lint 时追加;前缀 5 种(PRD §4.6 路径 B 注释):');
  out.push('  - `**Init**`:项目初始化');
  out.push('  - `**Ingest**`:inbox → raw 迁移 + 知识页生成');
  out.push('  - `**Creation**`:query 落档为 analysis 页(G11 M1)');
  out.push('  - `**LintFix**`:`--fix` 模式确定性结构修复');
  out.push('  - `**LintProposal**`:`--fix` 模式语义级问题(仅提案)');
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd() + '\n';
}

/**
 * 解析 file 的「显示名」:优先用 file.slug,否则 fallback 到 path basename 去扩展名
 * v0.6.0 (issue #4 fix):旧版用 path basename,slug 重命名后 wikilink 指向不存在文件
 */
function resolveDisplaySlug(f) {
  if (f.slug) return f.slug;
  const ext = path.extname(f.path);
  return path.basename(f.path, ext);
}

/**
 * 解析 file 的「目标 raw 文件名」:优先用 file.slug(扩展名保留),否则 fallback target_raw_path / path basename
 * 用于 log.md **Ingest** 行的 `→ raw/<subdir>/<name>` 段
 */
function resolveTargetFileName(f) {
  if (f.slug) {
    const ext = path.extname(f.path);
    return ext ? `${f.slug}${ext}` : f.slug;
  }
  if (f.target_raw_path) return path.basename(f.target_raw_path);
  return path.basename(f.path);
}

/**
 * 构造本次 ingest 的日志条目
 * 形如(无 entity/concept):
 *   **Ingest**: inbox/foo.pdf → raw/06_功能安全/foo-slug.pdf (+ .converted.md);新建 foo-slug
 * 形如(有 entity/concept,v0.6.6 PR-C #30):
 *   **Ingest**: inbox/foo.pdf → raw/06_功能安全/foo-slug.pdf (+ .converted.md);新建 foo-slug + entities/person/andrew-ng.md + concepts/field/ai-engineering-skills.md
 */
function buildEntries(files) {
  const lines = [];
  for (const f of files) {
    const inboxName = path.basename(f.path); // inbox 来源保留原文件名
    const slug = resolveDisplaySlug(f);
    const targetName = resolveTargetFileName(f);
    const sub = f.target_subdir || '?';
    const target = `raw/${sub}/${targetName}`;
    let entry = `**Ingest**: inbox/${inboxName} → ${target}`;
    if (f.converted_path) entry += ` (+ .converted.md)`;
    entry += ';新建 ';
    entry += slug;
    // v0.6.6 PR-C #30:追加 entity / concept 抽取结果
    // 元素 schema: {type, slug, title?} 与 build-related-pages.js:697-700 对齐
    const extras = buildEntityConceptSuffix(f);
    if (extras) entry += ' ' + extras;
    lines.push(entry);
  }
  return lines;
}

/**
 * v0.6.6 (issue #30 fix, PR-C):把 f.entities[] / f.concepts[] 转成
 * log.md 行末的 `+ entities/<dir>/<slug>.md + concepts/<dir>/<slug>.md` 段。
 * type 子类 `entity.person` → 目录 `person`(剥 `entity.` 前缀);`concept.field` → `field`(剥 `concept.` 前缀);
 * 与 doc/template/page-log.md 模板示例对齐。
 */
function buildEntityConceptSuffix(f) {
  const parts = [];
  const entities = Array.isArray(f.entities) ? f.entities : [];
  for (const e of entities) {
    if (!e || typeof e !== 'object') continue;
    const slug = e.slug;
    const type = e.type;
    if (!slug || !type) continue;
    const dir = String(type).replace(/^entity\./, '');
    parts.push(`entities/${dir}/${slug}.md`);
  }
  const concepts = Array.isArray(f.concepts) ? f.concepts : [];
  for (const c of concepts) {
    if (!c || typeof c !== 'object') continue;
    const slug = c.slug;
    const type = c.type;
    if (!slug || !type) continue;
    const dir = String(type).replace(/^concept\./, '');
    parts.push(`concepts/${dir}/${slug}.md`);
  }
  if (!parts.length) return '';
  return '+ ' + parts.join(' + ');
}

/**
 * 构造 P1-4 entries 预览数组(每个元素含 file / action / summary)
 * action 判定:
 *   - skipped:  f.dedupe_key 非空且已在 log.md 中出现 → 跳过
 *   - merged:   wasMerged=true(本次追加到已有当天节)
 *   - added:    wasMerged=false(本次新建当天节)
 */
function buildEntriesPreview(files, sectionsOrFlag, today) {
  // 兼容两种调用:
  //   - buildEntriesPreview(files, sections, today) 旧调用(忽略)
  //   - buildEntriesPreview(files, { _wasMerged: boolean }, today) 新调用
  let wasMerged = false;
  if (sectionsOrFlag && typeof sectionsOrFlag === 'object' && '_wasMerged' in sectionsOrFlag) {
    wasMerged = !!sectionsOrFlag._wasMerged;
  } else if (Array.isArray(sectionsOrFlag)) {
    wasMerged = sectionsOrFlag.some(s => s.date === today);
  }
  const preview = [];
  for (const f of files) {
    const slug = resolveDisplaySlug(f);
    const targetName = resolveTargetFileName(f);
    const sub = f.target_subdir || '?';
    const target = `raw/${sub}/${targetName}`;
    let summary;
    let action;
    if (f.dedupe_key && f.skipped_dedupe) {
      action = 'skipped';
      summary = `dedupe_key 已存在: ${f.dedupe_key}`;
    } else if (wasMerged) {
      action = 'merged';
      summary = `追加到 [${today}] 节:${slug} → ${target}`;
    } else {
      action = 'added';
      summary = `新建 [${today}] 节:${slug} → ${target}`;
    }
    // v0.6.6 (issue #30, PR-C):summary 同步含 entity/concept 列表
    const suffix = buildEntityConceptSuffix(f);
    if (suffix) summary += ' ' + suffix;
    preview.push({ file: f.path, action, summary });
  }
  return preview;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const project = path.resolve(args.project);
  const dryRun = !args.apply;

  const batch = await readJson(args.batch);
  const logPath = path.join(project, 'knowledge', 'log.md');
  const today = todayDate(batch.started_at || nowIso());
  const entries = buildEntries(batch.files);

  let existing = '';
  if (await fs.access(logPath).then(() => true).catch(() => false)) {
    existing = await fs.readFile(logPath, 'utf8');
  }

  const { fm, body } = parseFrontmatter(existing);
  const sections = parseLogSections(body);

  // 找到今天这一节;若不存在 → 新增(最新在前)
  const idx = sections.findIndex(s => s.date === today);
  if (idx === -1) {
    sections.unshift({ date: today, content: entries });
  } else {
    // 已存在 → 在该节顶部追加(最新在前)
    sections[idx].content = [...entries, ...sections[idx].content];
  }

  // 按日期降序排序(最新在前)
  sections.sort((a, b) => b.date.localeCompare(a.date));

  const newBody = renderLogSections(sections);
  const newContent = fm ? renderFrontmatterBlock(fm) + '\n' + newBody : newBody;

  // P1-4 批次 3: 构造 entries 预览数组(action 判定基于"插入前"已存在的 sections)
  // 注意:上面已经 unshift 了 today,所以这里用一个备份判断"插入前是否已存在"
  const wasMerged = idx !== -1;
  const entriesPreview = buildEntriesPreview(batch.files, { _wasMerged: wasMerged }, today);

  const result = {
    dry_run: dryRun,
    date: today,
    entries_added: entries.length,
    entries: entriesPreview,
    log_path: logPath.replace(/\\/g, '/'),
  };
  if (!dryRun) {
    try {
      await fs.writeFile(logPath, newContent, 'utf8');
      result.written = true;
    } catch (e) {
      console.error(`ERROR: 写 log.md 失败: ${e.message}`);
      process.exit(2);
    }
  }

  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(2);
});
