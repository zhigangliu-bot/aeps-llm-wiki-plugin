#!/usr/bin/env node
/**
 * lint.js — aeps-llm-wiki-lint:knowledge/ 全量机械体检 + --fix 确定性修复
 * (实现权威:doc/design/implement-lint.md v0.1.1 冻结;上游 PRD §4.4 + AC-4 / design §5 / §6.4)
 *
 * Usage:
 *   node scripts/lint/lint.js --project <用户工程根> [--fix] [--json]
 *
 * 规则定稿表(implement-lint.md §2):
 *   C1    FAIL  frontmatter 必填 + 类型(ajv + frontmatter.schema.json 先验 + §2.1 per-type 补充表)
 *   C1t   WARN  tags 数量 <5 / >10,或缺 docform/ + domain/ 必填轴(含单条非 6 轴字典格式)
 *   C2    FAIL  `## 摘要` / `## Summary` H2 残留
 *   C3    FAIL  source 3 节骨架(重点摘录 / 我的思考 / 总结:最有收获的一句话)
 *   C5    FAIL  sources 分治(M2A N4):analysis / synthesis / comparison 必填非空;
 *               其余 type(source / entity.* / concept.*)出现 sources → FAIL(--fix 删除)
 *   C6    WARN  synthesis sources_count < 3
 *   C7    FAIL  analysis sources_used 每条解析到真实 knowledge/ 下 .md 页面
 *   C8    WARN  `> 引用:` 行 wikilink Set ≠ sources_used Set
 *   C9    FAIL  半成品骨架页(§2.4 模板逐字行排除法)
 *   C15.4 FAIL  analysis 正文存在 `> 引用:` 行(AC-12:任意位置,习惯文末)
 *   C15.5 WARN  标准 markdown 链接残留(--fix 转 wikilink;page-source.md「C15.5 反转」命名)
 *   C17   FAIL  模板一致性(运行时读 <project>/doc/templates/page-*.md,§2.2 子序列)
 *   C18   FAIL  source 三字段一致性矛盾(claude-native + converted_path 非 null / native_text true +
 *               converted_path 非 null / 真转换器但 native_text ≠ false;claude-native 豁免第 3 条,issue #41)
 *   C19   WARN  路径 3/4 converter 但 log.md 无含原文件名的 **Ingest** 行
 *   C20   软约束 source 自由追加节清单(不 FAIL,进 JSON `c20_free_sections` + 文本报告)
 *   C21   WARN  source converted_path 副本图片链接 resolve(AC-16;悬空单列,http(s) 跳过)
 *   §2.3  proposal 孤儿 / 陈旧 / 漏链 / 命名飘 / 矛盾 hint(矛盾判定归 LLM,脚本零产出;
 *         孤儿对 analysis 豁免 overview.md / index.md 反链,issue #43)
 *   C4 编号保留空缺不复用(v0.5.6 起 analyses 不校验 H2 骨架,被 C15.4 取代)
 *
 * exit code: 0 成功(含 wiki 为空)/ 1 用法或环境错误 / 2 存在 FAIL(--fix 后仍剩也为 2)
 * stdout: --json 时 JSON 报告(§1.1 契约),否则人读文本;诊断 / 进度到 stderr
 *
 * 边界(§0.2):
 *   - 无 --fix 零写入;--fix 只 patch 确定性结构项 + 追加 log **LintFix** 行
 *   - 保留 4 文件(index / overview / glossary / log,任意层级按 basename)与 knowledge/.aeps-state/ 不扫
 *   - stale_after 未填一律静默跳过(不报陈旧、不 WARN;非 ISO 不猜)
 *   - 模板缺失 → C9/C17 降级 WARN 并注明,不 crash
 *   - 0 新 npm 依赖(js-yaml / ajv 已有;纯 node:fs / node:path)
 *   - 用户工程根一律 --project 显式传入,代码中无绝对路径
 */

import { promises as fs } from 'node:fs';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { requireDeps } from '../lib/preflight.js';

// js-yaml 在 main 内经 requireDeps 校验后加载(模块级声明,splitFrontmatter / applyFix 共用)
let yaml = null;

// ---------- 常量(权威 = implement-lint.md §2 / frontmatter-spec §4 / §11.7) ----------

// 保留 4 文件(任意层级按 basename 豁免,不扫)
const RESERVED_FILENAMES = new Set(['index.md', 'overview.md', 'glossary.md', 'log.md']);

// C5 sources 分治(M2A N4):三综合类必填,其余 type 禁止
const SYNTH_TYPES = new Set(['analysis', 'comparison', 'synthesis']);

// §2.1 C1 per-type 必填表(全部行 + per-type 追加行;与 frontmatter.schema.json allOf 对齐兜底)
const C1_COMMON_REQUIRED = ['type', 'updated', 'title', 'description', 'tags'];
const C1_TYPE_EXTRA = {
  source: ['resource', 'format', 'converter', 'native_text', 'converted_path', 'source_file'],
  analysis: ['answer_to', 'sources_used', 'sources_count', 'summary'],
  synthesis: ['sources_count', 'summary'],
  comparison: ['sources', 'sources_count', 'summary'],
};

// §4 C1 缺字段可补占位白名单(其余 converter / converted_path / source_file / answer_to / sources_used / resource 值语义未知 → 提案)
const C1_FILLABLE = new Set(['updated', 'title', 'description', 'tags', 'sources_count', 'summary']);

// tags 质量口径(对齐 frontmatter.schema.json tags items pattern + tag-spec §1.2 六轴)
const TAG_VALUE_RE = /^(?:domain|layer|phase|docform|maturity|tec)\/[a-z0-9][a-z0-9-]*$/;
const TAG_REQUIRED_AXES = ['docform', 'domain'];
const TAGS_MIN = 5;
const TAGS_MAX = 10;

// 真转换器集合:路径 3/4 converter(C19;对齐 frontmatter.schema.json converter enum,排除 null 与 claude-native)。
// C18 第 3 条同用此集合:仅真转换器要求 native_text === false;claude-native 表示「Claude 原生直读无副本」,
// 与 native_text 正交而非互斥,豁免第 3 条(issue #41:否则 path 1/2 默认合法组合全部误报)
const C19_CONVERTERS = new Set(['pyoffice', 'anydoc', 'docling', 'libreoffice', 'paddleocr']);

// C21:detail 图片名列表上限(超过截断为「前 5 个, 等 N 个」,防大副本刷屏)
const C21_DETAIL_MAX = 5;

// C9 生成区块 H2 key 集(gen-page.js GENERATED_H2_PATTERNS 同源,归一到括号前 key;
// 命中即整节不计实质行,起至下一 H1/H2 或文末,§2.4)
const GENERATED_SECTION_KEYS = new Set(['相关页面', '维护说明', '关联导引', '来源资料', '字段一致性 lint']);

// C17 已知「模板必有」家族 key(§2.2 验收基准;模板运行时提取后按此过滤,
// 使 page-source.md 的 `## 阅读路线` 等自由占位节不进必选表)
const C17_KNOWN_KEYS = new Set(['重点摘录', '我的思考', '总结:最有收获的一句话', '相关页面', '维护说明', '关联导引', '来源资料']);

// C3 source 3 节 + source 模板完整规范顺序(--fix 追加锚点用)
const C3_REQUIRED = ['重点摘录', '我的思考', '总结:最有收获的一句话'];
const C17_SOURCE_ORDER = [...C3_REQUIRED, '相关页面', '维护说明'];

// 语义级规则(fail/warn 不修,只在报告 + 文本模式出 **LintProposal** 提案行,§0.1 / §4)
const SEMANTIC_FAIL_RULES = new Set(['C5', 'C7', 'C9', 'C17', 'C18']);
const SEMANTIC_WARN_RULES = new Set(['C1t', 'C19', 'C21']);

// H2 残留 / 引用行 / wikilink / md 链接
const C2_H2_RE = /^##\s*(摘要|Summary)\s*$/;
const CITE_LINE_RE = /^>\s*引用[:：]/;
const WIKILINK_RE = /\[\[([^\[\]]+?)\]\]/g;
const MD_LINK_RE = /(!?)\[([^\]\n]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;
// C21 图片引用:![](target) —— alt 允许为空(docling 抽图输出即空 alt,与 MD_LINK_RE 唯一差别在此)
const C21_IMG_RE = /!\[[^\]\n]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;
const LOG_DATE_H2_RE = /^##\s+\[(\d{4}-\d{2}-\d{2})\]\s*$/;

// ---------- 小工具 ----------

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function parseArgs(argv) {
  const args = { project: null, fix: false, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--fix') args.fix = true;
    else if (a === '--json') args.json = true;
  }
  return args;
}

/** 归一相对路径:反斜杠 → 正斜杠,剥前导 ./ 与 knowledge/ */
function normalizeRel(p) {
  let s = String(p ?? '').trim().replace(/\\/g, '/');
  while (s.startsWith('./')) s = s.slice(2);
  if (s.startsWith('knowledge/')) s = s.slice('knowledge/'.length);
  return s;
}

function stemOf(rel) {
  const base = normalizeRel(rel).split('/').pop() || '';
  return base.replace(/\.md$/i, '');
}

/**
 * 递归收集 dir 下 .md(跳过 .aeps-state/ 目录段;目录缺失 / 路径段是普通文件 → null)。
 * 保留 4 文件豁免在调用侧按 basename 过滤(需要 reserved_skipped 计数)。
 */
async function listMarkdownFiles(dir) {
  const out = [];
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch (e) {
    // ENOENT:目录不存在;ENOTDIR:knowledge/ 路径段是普通文件 —— 契约同义"目录不存在" → G-L1
    if (e.code === 'ENOENT' || e.code === 'ENOTDIR') return null;
    throw e;
  }
  for (const ent of entries) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      if (ent.name === '.aeps-state') continue; // plugin 状态目录,永不扫
      const sub = await listMarkdownFiles(full);
      if (sub) out.push(...sub);
    } else if (ent.isFile() && ent.name.toLowerCase().endsWith('.md')) {
      out.push(full);
    }
  }
  return out;
}

/** frontmatter 切分:'---\\n<yaml>---\\n<body>';无 frontmatter / 非对象 / YAML 失败 → fm = null */
function splitFrontmatter(text) {
  const m = text.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  if (!m) return { fmRaw: null, fm: null, body: text, fmError: 'frontmatter 缺失' };
  try {
    const fm = yaml.load(m[1]);
    if (fm === null || typeof fm !== 'object' || Array.isArray(fm)) {
      return { fmRaw: `---\n${m[1]}\n---\n`, fm: null, body: m[2], fmError: 'frontmatter 不是键值映射对象' };
    }
    return { fmRaw: `---\n${m[1]}\n---\n`, fm, body: m[2], fmError: null };
  } catch (e) {
    return { fmRaw: `---\n${m[1]}\n---\n`, fm: null, body: m[2], fmError: `YAML 解析失败: ${e.message}` };
  }
}

/** H2 行 → 匹配 key:`## ` 后文本含 `(` 时截断到 `(` 前(§2.2 前缀匹配口径) */
function h2Key(line) {
  const m = line.match(/^##\s+(.+?)\s*$/);
  if (!m) return null;
  const t = m[1];
  const i = t.indexOf('(');
  return (i > 0 ? t.slice(0, i) : t).trim();
}

function isBigHeading(line) {
  return /^#{1,2}\s+/.test(line); // H1/H2(C9 生成区块止界,同 gen-page stripGeneratedH2s)
}

function isH2Line(line) {
  return /^##\s+/.test(line);
}

/** 正文 H2 key 序列 */
function h2KeysOf(body) {
  return body.split('\n').map((l) => (isH2Line(l) ? h2Key(l) : null)).filter(Boolean);
}

/** 子序列判定:required 须为 page 的子序列(自由追加节不破坏) */
function isSubsequence(required, pageKeys) {
  let i = 0;
  for (const k of pageKeys) {
    if (i < required.length && k === required[i]) i++;
  }
  return i === required.length;
}

/** 正文 wikilink 目标 stem 集:裸文件名口径(basename 去 .md);[[target|alias]] 的 alias 不参与解析 */
function wikilinkTargets(text) {
  const out = [];
  for (const m of text.matchAll(WIKILINK_RE)) {
    const raw = m[1].split('|')[0].trim();
    if (!raw) continue;
    const stem = raw.replace(/\.md$/i, '').split('/').pop().trim();
    if (stem) out.push(stem);
  }
  return out;
}

/** 剥掉全部 wikilink 后的正文(漏链扫描:wikilink 内的提及不算提及) */
function stripWikilinks(text) {
  return text.replace(WIKILINK_RE, ' ');
}

function countOccurrences(hay, needle) {
  if (!needle) return 0;
  let n = 0;
  let i = 0;
  while ((i = hay.indexOf(needle, i)) !== -1) {
    n++;
    i += needle.length;
  }
  return n;
}

/** Levenshtein 距离(命名飘扫描;文件名短串,DP 开销可忽略) */
function levenshtein(a, b) {
  const m = a.length;
  const n = b.length;
  if (Math.abs(m - n) > 2) return 3; // 命名飘阈值 2,差距过大直接剪枝
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return prev[n];
}

// ---------- type / 目录 → 模板名(gen-page.js 同名映射) ----------

function templateNameForType(type) {
  if (!type || typeof type !== 'string') return null;
  if (type === 'source') return 'page-source.md';
  if (type.startsWith('entity.')) return 'page-entity.md';
  if (type.startsWith('concept.')) return 'page-concept.md';
  if (type === 'analysis' || type === 'comparison' || type === 'synthesis') return `page-${type}.md`;
  return null;
}

/** type 缺失 / 非法时的目录兜底(与 knowledge/ 顶层目录 1:1 绑死同源) */
function templateNameForDir(relDir) {
  const top = (relDir || '').split('/')[0];
  const map = {
    sources: 'page-source.md',
    entities: 'page-entity.md',
    concepts: 'page-concept.md',
    analyses: 'page-analysis.md',
    comparisons: 'page-comparison.md',
    syntheses: 'page-synthesis.md',
  };
  return map[top] || null;
}

/**
 * 读 <project>/doc/templates/page-*.md(C17 / C9 同源):
 *   h2Keys  — 模板 H2 key 序列(过滤到 C17_KNOWN_KEYS 必选家族)
 *   lineSet — 模板正文行集合(trim 后,§2.4 逐字行排除法)
 * 模板缺失 → { missing: true }(C9/C17 降级 WARN,不 crash)
 */
async function loadTemplates(project, names) {
  const map = {};
  for (const name of names) {
    try {
      const txt = await fs.readFile(path.join(project, 'doc', 'templates', name), 'utf8');
      const cleaned = txt.replace(/\r\n/g, '\n').replace(/^(?:<!--[\s\S]*?-->\s*\n)+/, '');
      const { body } = splitFrontmatter(cleaned);
      map[name] = {
        missing: false,
        h2Keys: h2KeysOf(body).filter((k) => C17_KNOWN_KEYS.has(k)),
        lineSet: new Set(body.split('\n').map((l) => l.trim()).filter((l) => l !== '')),
      };
    } catch {
      map[name] = { missing: true, h2Keys: [], lineSet: new Set() };
    }
  }
  return map;
}

// ---------- 主流程(ajv 编译失败 → G-L2 exit 1,不带病扫) ----------

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.project) {
    console.error('ERROR: --project <用户工程根> 必填(显式传,脚本内无默认值)');
    process.exit(1);
  }
  await requireDeps({ 'js-yaml': 'js-yaml', ajv: 'ajv' });
  const yamlMod = await import('js-yaml');
  yaml = yamlMod.default;
  const Ajv = (await import('ajv')).default;

  // ajv 编译(G-L2:schema 坏 → exit 1)
  let validate;
  try {
    const schemaPath = path.resolve(import.meta.dirname, '..', '..', 'doc', 'schema', 'frontmatter.schema.json');
    const schema = JSON.parse(readFileSync(schemaPath, 'utf8'));
    // ajv 8 默认仅支持 draft-07;本 schema 标 draft 2020-12 但实际未用 draft 关键字,
    // 去掉 $schema 走默认 meta 即可 compile(与 ingest/build-related-pages.js 同款口径)。
    delete schema.$schema;
    const ajv = new Ajv({ allErrors: true, strict: false });
    validate = ajv.compile(schema);
  } catch (e) {
    console.error(`ERROR: ajv 编译 frontmatter.schema.json 失败(疑似 spec 与 schema 漂移,G-L2): ${e.message}`);
    process.exit(1);
  }

  const project = path.resolve(args.project);
  const knowledgeDir = path.join(project, 'knowledge');

  // ---- 第一趟:全量扫描(读页 + 逐页规则 + 跨页机械扫描) ----
  let s = await runScan(project, knowledgeDir, validate);
  if (s === null) {
    console.error(`ERROR: knowledge/ 目录不存在: ${knowledgeDir}(先跑 /aeps-llm-wiki-init 初始化 vault,G-L1)`);
    process.exit(1);
  }

  // ---- --fix(确定性修复;语义级永远只提案) ----
  const fixed = [];
  if (args.fix) {
    for (const rec of s.records) {
      await applyFix(rec, s.ctx, fixed);
    }
    if (fixed.length > 0) {
      const logInfo = appendLintFixToLog(knowledgeDir, fixed);
      console.error(`[lint] log.md ${logInfo.action}: ${logInfo.line}`);
    }
    // 第二趟:剩余项口径(SKILL 步骤 12「--fix 后仍剩 FAIL → exit 2」按 fix 后状态判定)
    s = await runScan(project, knowledgeDir, validate);
  }

  // ---- 报告(§1.1 契约;fails/warns/proposals 反映最终状态) ----
  const report = {
    pages_scanned: s.records.length,
    reserved_skipped: s.reservedSkipped,
    fails: s.fails,
    warns: s.warns,
    proposals: s.proposals,
    stats: { fail: s.fails.length, warn: s.warns.length, proposal: s.proposals.length, fixed: fixed.length },
  };
  if (args.fix) report.fixed = fixed;
  if (s.c20.length > 0) report.c20_free_sections = s.c20; // 加性字段:C20 溯源自检数据(SKILL.md 消费)

  console.error(`[lint] scan 完成: pages=${s.records.length} reserved_skipped=${s.reservedSkipped} fail=${s.fails.length} warn=${s.warns.length} proposal=${s.proposals.length} fixed=${fixed.length}`);
  if (s.records.length === 0) {
    console.error('[lint] wiki 为空,先跑 /aeps-llm-wiki-init + ingest 再 lint');
  }

  if (args.json) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    printTextReport(report, { fix: args.fix, project });
  }
  process.exit(s.fails.length > 0 ? 2 : 0);
}

/**
 * 单趟扫描:读页 + 切 frontmatter → 逐页规则评估 → 跨页机械扫描。
 * 返回 { records, reservedSkipped, fails, warns, proposals, c20, ctx };
 * knowledge/ 不存在 → null(G-L1)。
 */
async function runScan(project, knowledgeDir, validate) {
  const files = await listMarkdownFiles(knowledgeDir);
  if (files === null) return null;

  // 读页 + 切 frontmatter
  const records = [];
  let reservedSkipped = 0;
  for (const abs of files) {
    const rel = normalizeRel(path.relative(knowledgeDir, abs));
    if (RESERVED_FILENAMES.has(path.basename(rel))) {
      reservedSkipped++;
      continue;
    }
    let text;
    try {
      text = await fs.readFile(abs, 'utf8');
    } catch (e) {
      console.error(`WARN: 读文件失败跳过 ${rel}: ${e.message}`);
      continue;
    }
    text = text.replace(/\r\n/g, '\n');
    const { fmRaw, fm, body, fmError } = splitFrontmatter(text);
    const type = fm && typeof fm.type === 'string' ? fm.type : null;
    const dir = rel.includes('/') ? rel.slice(0, rel.lastIndexOf('/')) : '';
    records.push({
      rel, abs, stem: stemOf(rel), dir, text, fmRaw, fm, body, fmError, type,
      templateName: templateNameForType(type) || templateNameForDir(dir),
    });
  }

  // 跨页索引(C7 / C15.5 / 机械扫描共用)
  const ctx = {
    knowledgeDir,
    relSet: new Set(records.map((r) => r.rel)),
    stemSet: new Set(records.map((r) => r.stem)),
    logContent: await fs.readFile(path.join(knowledgeDir, 'log.md'), 'utf8').catch(() => ''),
    // 顶层 index / overview 正文(保留文件不进 records;孤儿扫描对 analysis 的豁免反链源,issue #43)
    indexContent: await fs.readFile(path.join(knowledgeDir, 'index.md'), 'utf8').catch(() => ''),
    overviewContent: await fs.readFile(path.join(knowledgeDir, 'overview.md'), 'utf8').catch(() => ''),
  };

  // 模板运行时读取(C17 / C9 同源)
  const tplNames = [...new Set(records.map((r) => r.templateName).filter(Boolean))];
  const templates = await loadTemplates(project, tplNames);

  // 逐页规则评估
  const fails = [];
  const warns = [];
  const proposals = [];
  const c20 = [];
  for (const rec of records) {
    evalPage(rec, { validate, templates }, ctx, fails, warns, c20);
  }

  // C21:source converted_path 副本图片链接(异步读 raw/ 副本;AC-16,只读零写入)
  await convertedScan(records, project, warns);

  // 跨页机械扫描(§2.3,全部 proposal 级)
  mechanicalScan(records, proposals, ctx);

  return { records, reservedSkipped, fails, warns, proposals, c20, ctx };
}

// ---------- 逐页规则评估 ----------

function evalPage(rec, tools, ctx, fails, warns, c20) {
  const { validate, templates } = tools;
  const fm = rec.fm;
  const type = rec.type;
  const c1Details = [];
  const c1Missing = new Set();
  let c1tDetail = null;
  const coerce = [];
  const c2Hits = [];
  let c7FailCount = 0;

  // ---- C2:`## 摘要` / `## Summary` H2 残留(全 type)----
  const lines = rec.body.split('\n');
  lines.forEach((line, idx) => {
    if (C2_H2_RE.test(line)) c2Hits.push({ idx, title: line.trim() });
  });
  for (const hit of c2Hits) {
    fails.push(entry('C2', rec, `H2 残留「${hit.title}」——内容应迁 frontmatter summary(--fix 可迁移)`));
  }

  // ---- C1 / C1t ----
  if (fm === null) {
    c1Details.push(rec.fmError);
  } else {
    const ok = validate(fm);
    if (!ok) {
      const tagQualityIssues = [];
      for (const e of validate.errors || []) {
        const p = e.instancePath || '';
        if (e.keyword === 'required' || e.keyword === 'if' || e.keyword === 'then') {
          // 必填性一律以 §2.1 per-type 表为准(下方循环)——schema 的 if/then 分支在
          // type 缺失/错值时会对所有分支集体触发 required 噪声,不能直接采信;
          // `if` 关键字是分支父错误,同样忽略。
          continue;
        }
        if ((e.keyword === 'minItems' || e.keyword === 'maxItems' || e.keyword === 'pattern') && (p === '/tags' || p.startsWith('/tags/'))) {
          // tags 数量 / 单条格式越界 → C1t WARN 通道(§2 冻结:C1t WARN,不进 C1 FAIL)
          tagQualityIssues.push(`${p || '/tags'} ${e.message}`);
        } else {
          c1Details.push(`字段类型/取值错误 ${p || '/'} ${e.message}`);
        }
      }
      if (tagQualityIssues.length) c1tDetail = joinParts(tagQualityIssues);
    }
    // §2.1 per-type 补充表(ajv required 之外再兜一道,缺一 FAIL 一条)
    const required = [...C1_COMMON_REQUIRED, ...(C1_TYPE_EXTRA[type] || [])];
    for (const f of required) {
      if (!(f in fm)) c1Missing.add(f);
    }
    for (const f of c1Missing) c1Details.push(`缺少必填字段 ${f}`);

    // C1t:tags 质量手工复核(数量 + 必填轴 + 单条 6 轴格式)
    if (Array.isArray(fm.tags)) {
      const issues = [];
      if (fm.tags.length < TAGS_MIN) issues.push(`tags ${fm.tags.length} 条 < ${TAGS_MIN}`);
      if (fm.tags.length > TAGS_MAX) issues.push(`tags ${fm.tags.length} 条 > ${TAGS_MAX}`);
      const axes = new Set(fm.tags.map((t) => String(t).split('/')[0]));
      for (const ax of TAG_REQUIRED_AXES) {
        if (!axes.has(ax)) issues.push(`缺必填轴 ${ax}/`);
      }
      const bad = fm.tags.filter((t) => !TAG_VALUE_RE.test(String(t)));
      if (bad.length) issues.push(`非 6 轴字典格式: ${bad.join(', ')}`);
      if (issues.length) c1tDetail = joinParts(issues);
    }

    // --fix 强转候选(§4 C1 类型错位)
    if (typeof fm.tags === 'string') coerce.push({ field: 'tags', action: 'tags 字符串 → 单元素数组' });
    if (typeof fm.sources_count === 'string' && /^\d+$/.test(fm.sources_count.trim())) {
      coerce.push({ field: 'sources_count', action: 'sources_count 数字字符串 → 整数' });
    }
    if (fm.native_text === 'true' || fm.native_text === 'false') {
      coerce.push({ field: 'native_text', action: 'native_text "true"/"false" → 布尔' });
    }
  }
  for (const d of c1Details) fails.push(entry('C1', rec, d));
  if (c1tDetail) warns.push(entry('C1t', rec, `${c1tDetail}(tag-spec 六轴口径,--fix 不代定 tags)`));

  if (fm !== null) {
    // ---- C3:source 3 节骨架 ----
    if (type === 'source') {
      const keys = new Set(h2KeysOf(rec.body));
      for (const k of C3_REQUIRED) {
        if (!keys.has(k)) fails.push(entry('C3', rec, `缺少 source 必备节「## ${k}」(--fix 追加占位 H2)`));
      }
      // ---- C20:自由追加节清单(软约束,不 FAIL)----
      const beforeMaint = [];
      for (const line of lines) {
        if (isH2Line(line)) {
          const k = h2Key(line);
          if (k === '维护说明') break;
          beforeMaint.push(k);
        }
      }
      // 3 节必选与脚本生成区块不算自由节(gen-page 产出非 LLM 所写,§6.4 语义)
      const free = beforeMaint.filter((k) => !C3_REQUIRED.includes(k) && !GENERATED_SECTION_KEYS.has(k));
      if (free.length) c20.push({ file: rec.rel, sections: free });
    }

    // ---- C5:sources 分治(M2A N4,用户拍板 2026-09-17)----
    // analysis / synthesis / comparison(三综合类)→ sources 必填非空(对象数组);
    // 其余 type(source / entity.* / concept.*)→ sources 禁止(--fix 直接删除字段)。
    if (SYNTH_TYPES.has(type)) {
      if (!('sources' in fm)) {
        fails.push(entry('C5', rec, `${type} 必填 sources(字段缺失;值语义未知,--fix 不自动补)`));
      } else if (Array.isArray(fm.sources) && fm.sources.length === 0) {
        fails.push(entry('C5', rec, `${type} sources 为空数组(值语义未知,--fix 不自动补)`));
      }
    } else if ('sources' in fm) {
      fails.push(entry('C5', rec, `type=${type} 禁止 sources 字段(N4 分治:物理定位由 source 页顶层 resource 承载;--fix 删除该字段)`));
    }

    // ---- C6:synthesis sources_count < 3 ----
    if (type === 'synthesis' && typeof fm.sources_count === 'number' && fm.sources_count < 3) {
      warns.push(entry('C6', rec, `sources_count=${fm.sources_count} < 3`));
    }

    // ---- C7 / C15.4 / C8:analysis ----
    if (type === 'analysis') {
      const citeIdx = lines.findIndex((l) => CITE_LINE_RE.test(l.trim()));
      // C15.4:引用行必须存在(AC-12:正文任意位置,习惯文末)
      if (citeIdx === -1) {
        fails.push(entry('C15.4', rec, '缺少「> 引用:」行(--fix 在 C7 通过时按 sources_used 生成)'));
      }
      // C7:sources_used 每条解析到真实页
      if (Array.isArray(fm.sources_used)) {
        for (const e of fm.sources_used) {
          if (!resolveUsedEntry(e, ctx)) {
            c7FailCount++;
            fails.push(entry('C7', rec, `sources_used 条目无法解析到真实页面: ${String(e)}(删哪条语义未知,--fix 不动)`));
          }
        }
      }
      // C8:引用行 wikilink Set vs sources_used Set
      if (citeIdx !== -1 && Array.isArray(fm.sources_used)) {
        const lineStems = wikilinkTargets(lines[citeIdx]);
        const usedStems = usedStemsOf(fm.sources_used);
        const missing = usedStems.filter((s) => !lineStems.includes(s));
        const extra = lineStems.filter((s) => !usedStems.includes(s));
        if (missing.length || extra.length) {
          warns.push(entry('C8', rec, `引用行与 sources_used 不一致(缺: ${joinParts(missing)};多: ${joinParts(extra)})`));
        }
      }
    }

    // ---- C18:source 三字段一致性矛盾 ----
    if (type === 'source') {
      const clauses = [];
      const hasConverted = fm.converted_path != null && fm.converted_path !== '';
      if (fm.converter === 'claude-native' && hasConverted) {
        clauses.push('converter: claude-native 但 converted_path 非 null');
      }
      if (fm.native_text === true && hasConverted) {
        clauses.push('native_text: true 但 converted_path 非 null');
      }
      if (C19_CONVERTERS.has(fm.converter) && fm.native_text !== false) {
        clauses.push('converter 非空但 native_text ≠ false(仅真转换器;claude-native 豁免)');
      }
      if (clauses.length) {
        fails.push(entry('C18', rec, `${joinParts(clauses)}(--fix 不自动改,语义级)`));
      }
      // ---- C19:路径 3/4 converter 需 log **Ingest** 行佐证 ----
      if (C19_CONVERTERS.has(fm.converter)) {
        const filename = ingestFilenameOf(fm);
        if (!filename) {
          warns.push(entry('C19', rec, `converter=${fm.converter}(路径 3/4)但无法从 source_file / resource 提取原文件名,无法核对 Ingest 日志`));
        } else {
          const hasIngest = ctx.logContent.split('\n')
            .some((l) => l.includes('**Ingest**') && l.includes(filename));
          if (!hasIngest) {
            warns.push(entry('C19', rec, `converter=${fm.converter}(路径 3/4)但 log.md 无含 ${filename} 的 **Ingest** 行(请补 log,--fix 不代写)`));
          }
        }
      }
    }
  }

  // ---- C17 / C9:模板一致性 + 半成品骨架页(模板缺失降级 WARN)----
  if (rec.templateName) {
    const tpl = templates[rec.templateName];
    if (tpl.missing) {
      warns.push(entry('C17', rec, `降级:模板缺失(${rec.templateName}),无法校验模板一致性(请 sync doc/templates/)`));
      warns.push(entry('C9', rec, `降级:模板缺失(${rec.templateName}),无法做逐字行排除判定`));
    } else {
      // C17:模板必有 H2 须为页面 H2 序列的子序列(自由追加节不破坏)
      if (tpl.h2Keys.length > 0 && !isSubsequence(tpl.h2Keys, h2KeysOf(rec.body))) {
        fails.push(entry('C17', rec, `模板必有 H2 缺失或顺序错乱,须为子序列: ${tpl.h2Keys.join(' → ')}(--fix 不代排骨架)`));
      }
      // C9:实质内容行数(§2.4 排除法)== 0 → FAIL
      let substantive = 0;
      let skipSection = false;
      for (const line of rec.body.split('\n')) {
        const t = line.trim();
        if (isBigHeading(t)) {
          const k = h2Key(t);
          skipSection = k !== null && GENERATED_SECTION_KEYS.has(k);
          continue; // 标题行不计
        }
        if (skipSection || t === '' || tpl.lineSet.has(t)) continue;
        substantive = 1;
        break; // 只需 > 0
      }
      if (substantive === 0) {
        fails.push(entry('C9', rec, '半成品骨架页:正文无实质内容(§2.4 模板逐字行排除法)——请走 ingest / query / synthesize 补正文,或拍板删页(--fix 不自动填)'));
      }
    }
  }

  // ---- C15.5:标准 markdown 链接残留(全 type;--fix 转 wikilink)----
  const mdLinks = findMdLinks(rec, ctx);
  if (mdLinks.count > 0) {
    warns.push(entry('C15.5', rec, `标准 markdown 链接残留 ×${mdLinks.count}: ${joinParts(mdLinks.samples, '; ')}(--fix 转 [[wikilink]])`));
  }

  // fix 阶段需要的中间结果挂到 record(单脚本拓扑:--fix 复用同一趟扫描结果)
  rec.fixCtx = { c1Missing: [...c1Missing], c1tDetail, coerce, c2Hits, c7FailCount };
  return { c1Missing, c7FailCount };
}

function entry(rule, rec, detail) {
  return { rule, file: rec.rel, detail };
}

function joinParts(arr, sep = '; ') {
  return arr.length ? arr.join(sep) : '(无)';
}

/** C7 条目解析:直接相对路径 → 后缀匹配 → 裸文件名 stem(三层,宽松机械口径) */
function resolveUsedEntry(e, ctx) {
  const n = normalizeRel(e);
  if (!n) return false;
  if (ctx.relSet.has(n)) return true;
  for (const rel of ctx.relSet) {
    if (rel.endsWith(`/${n}`)) return true;
  }
  return ctx.stemSet.has(stemOf(n));
}

/** sources_used 条目 → stem 列表(去重保序) */
function usedStemsOf(sourcesUsed) {
  const out = [];
  for (const e of sourcesUsed) {
    const s = stemOf(e);
    if (s && !out.includes(s)) out.push(s);
  }
  return out;
}

/** C19 原文件名:source_file wikilink 目标 basename,fallback resource basename */
function ingestFilenameOf(fm) {
  const m = String(fm.source_file ?? '').match(/\[\[([^\]|]+)/);
  let name = m ? m[1].trim() : String(fm.resource ?? '').split('|')[0].trim();
  if (!name) return null;
  name = name.replace(/\\/g, '/').split('/').pop().trim();
  return name || null;
}

// ---------- C21:source converted_path 副本图片链接 resolve(AC-16;WARN,无 --fix 行为) ----------

/**
 * 对 source 页 frontmatter converted_path(相对工程根,raw/ 下 `<basename>.converted.md`):
 *   - .converted.md 不存在 / 读失败 → 单独 WARN(converted_path 悬空)
 *   - 存在 → 提取全部 `![](...)` 图片引用,逐条按「相对 .converted.md 所在目录」resolve
 *     (docling 抽图落 `<basename>.converted_media/`,与副本同目录);任一目标不存在
 *     → 合并为一条 WARN(file = source 页,detail 列未 resolve 图名,> 5 截断「等 N 个」)
 *   - converted_path 为 null / 缺失 / 空串 → 跳过;http(s):// 图片引用跳过不查
 *   - 纯只读:不改副本、不改 raw/,--fix 无此项
 */
async function convertedScan(records, project, warns) {
  for (const rec of records) {
    const fm = rec.fm;
    if (!fm || rec.type !== 'source') continue;
    const cp = typeof fm.converted_path === 'string' ? fm.converted_path.trim() : '';
    if (!cp) continue; // null / 字段缺失 / 空串 → 跳过(原生路径无副本)
    const convertedAbs = path.resolve(project, normalizeRel(cp));
    let text;
    try {
      text = await fs.readFile(convertedAbs, 'utf8');
    } catch (e) {
      const why = e.code === 'ENOENT' ? '文件不存在' : `读取失败(${e.code})`;
      warns.push(entry('C21', rec, `converted_path 悬空(${why}): ${normalizeRel(cp)}(请重转或修正 converted_path)`));
      continue;
    }
    const convertedDir = path.dirname(convertedAbs);
    const missing = [];
    const seen = new Set(); // 同一引用去重保序(同一张图缺了不重复列)
    for (const m of text.matchAll(C21_IMG_RE)) {
      const target = m[1].trim();
      if (!target || /^https?:\/\//i.test(target)) continue; // 空目标 / http(s) 跳过
      if (seen.has(target)) continue;
      seen.add(target);
      try {
        await fs.access(path.resolve(convertedDir, target));
      } catch {
        missing.push(target);
      }
    }
    if (missing.length) {
      warns.push(entry('C21', rec, `副本图片链接未 resolve ×${missing.length}: ${joinParts(listWithCap(missing, C21_DETAIL_MAX), ', ')}(--fix 不改 raw 副本,请重转或补图)`));
    }
  }
}

/** C21 detail 图名列表:超过 cap 个截断为「前 cap 个, 等 N 个」 */
function listWithCap(arr, cap) {
  if (arr.length <= cap) return arr;
  return [...arr.slice(0, cap), `等 ${arr.length} 个`];
}

/** C15.5 扫描:正文(跳代码围栏)中解析到 knowledge 页的 md 链接 */
function findMdLinks(rec, ctx) {
  let count = 0;
  const samples = [];
  let inFence = false;
  for (const line of rec.body.split('\n')) {
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    for (const m of line.matchAll(MD_LINK_RE)) {
      if (m[1] === '!') continue; // 图片不转
      const stem = resolveMdTarget(m[3], rec, ctx);
      if (stem) {
        count++;
        if (samples.length < 3) samples.push(`[${m[2]}](${m[3]})`);
      }
    }
  }
  return { count, samples };
}

/** md 链接目标 → knowledge 页 stem;非 .md / http / 解析不到 → null(不转) */
function resolveMdTarget(target, rec, ctx) {
  let t = String(target).split('#')[0].trim();
  if (!t || /^(https?:|mailto:)/i.test(t) || !/\.md$/i.test(t)) return null;
  const relNorm = normalizeRel(t);
  const abs = path.resolve(ctx.knowledgeDir, rec.dir ? path.join(rec.dir, relNorm) : relNorm);
  const relFromKnowledge = normalizeRel(path.relative(ctx.knowledgeDir, abs));
  if (relFromKnowledge && !relFromKnowledge.startsWith('../') && relFromKnowledge !== '..' && ctx.relSet.has(relFromKnowledge)) {
    return stemOf(relFromKnowledge);
  }
  const stem = stemOf(relNorm);
  return ctx.stemSet.has(stem) ? stem : null;
}

// ---------- 跨页机械扫描(§2.3) ----------

function mechanicalScan(records, proposals, ctx) {
  const MAX_CONTRA_HINTS = 20; // ponytail: 矛盾候选对硬上限,防大 wiki 刷屏;真需要再按 domain 细分

  // wikilink 入链图(保留页不在 records,天然不作为链源)
  const linkSets = new Map(records.map((r) => [r.rel, new Set(wikilinkTargets(r.body))]));

  // 孤儿页:全 wiki 无任何其他页正文 [[basename]] 链入。
  // analysis 页豁免(issue #43):被顶层 overview.md / index.md 反链即不算孤儿 —— query 落档后
  // 由 overview「近期分析(analyses/)」节保证反链;保留 4 文件不进 records,须单独取其正文。
  const reservedLinkStems = new Set([
    ...wikilinkTargets(ctx.indexContent || ''),
    ...wikilinkTargets(ctx.overviewContent || ''),
  ]);
  for (const rec of records) {
    const isAnalysis = rec.type === 'analysis' || rec.dir.split('/')[0] === 'analyses';
    const linked = records.some((o) => o.rel !== rec.rel && linkSets.get(o.rel).has(rec.stem))
      || (isAnalysis && reservedLinkStems.has(rec.stem));
    if (!linked) {
      proposals.push({ kind: 'orphan', file: rec.rel, detail: `全 wiki 无任何其他页正文 [[${rec.stem}]] 链入(孤儿页)`, fixable: false });
    }
  }

  // 陈旧页:stale_after 已填且 <= now(§4.5.2);未填 / 非 ISO 一律静默跳过(零输出)
  const now = Date.now();
  for (const rec of records) {
    const v = rec.fm ? rec.fm.stale_after : null;
    if (typeof v !== 'string' || !v.trim()) continue;
    const t = Date.parse(v.trim());
    if (Number.isNaN(t)) continue;
    if (t <= now) {
      proposals.push({ kind: 'stale', file: rec.rel, detail: `stale_after=${v.trim()} 已过期(now >= stale_after 即陈旧)`, fixable: false });
    }
  }

  // 漏链:他页 basename / aliases 在本页正文(剥 wikilink 后)出现 ≥ 2 次但无对应 wikilink
  for (const rec of records) {
    const text = stripWikilinks(rec.body);
    for (const other of records) {
      if (other.rel === rec.rel) continue;
      if (linkSets.get(rec.rel).has(other.stem)) continue; // 已有 wikilink
      let mentions = countOccurrences(text, other.stem);
      for (const alias of aliasesOf(other)) {
        mentions += countOccurrences(text, alias);
      }
      if (mentions >= 2) {
        proposals.push({ kind: 'missing-link', file: rec.rel, detail: `提及 ${other.stem} ×${mentions} 但无 [[wikilink]]`, fixable: false });
      }
    }
  }

  // 命名飘:同目录内文件名 Levenshtein ≤ 2 或互为前缀(≥ 4 字符)
  const byDir = new Map();
  for (const rec of records) {
    if (!byDir.has(rec.dir)) byDir.set(rec.dir, []);
    byDir.get(rec.dir).push(rec);
  }
  for (const group of byDir.values()) {
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        const a = group[i].stem;
        const b = group[j].stem;
        const d = levenshtein(a, b);
        const prefixLen = Math.min(a.length, b.length);
        const sharedPrefix = a.slice(0, prefixLen) === b.slice(0, prefixLen) && (a.startsWith(b) || b.startsWith(a));
        if (d <= 2) {
          proposals.push({ kind: 'name-drift', file: group[i].rel, detail: `${a} 与 ${b} 命名相近(Levenshtein=${d} ≤ 2),疑似命名飘(合并 / 改名由用户拍板)`, fixable: false });
        } else if (sharedPrefix && prefixLen >= 4) {
          proposals.push({ kind: 'name-drift', file: group[i].rel, detail: `${a} 与 ${b} 互为前缀(≥ 4 字符),疑似命名飘(合并 / 改名由用户拍板)`, fixable: false });
        }
      }
    }
  }

  // 矛盾 hint:仅列同 topic(共享 domain/ 轴 tag)候选页对;判定由 LLM 在 SKILL.md 步骤做
  let hintCount = 0;
  for (let i = 0; i < records.length && hintCount < MAX_CONTRA_HINTS; i++) {
    for (let j = i + 1; j < records.length && hintCount < MAX_CONTRA_HINTS; j++) {
      const shared = sharedDomainTags(records[i], records[j]);
      if (shared.length) {
        proposals.push({
          kind: 'contradiction-hint',
          file: records[i].rel,
          detail: `与 ${records[j].stem} 同 domain(${shared.join(', ')})——仅候选对,矛盾判定由 LLM 完成`,
          fixable: false,
        });
        hintCount++;
      }
    }
  }
}

function aliasesOf(rec) {
  const a = rec.fm ? rec.fm.aliases : null;
  if (!Array.isArray(a)) return [];
  return a.filter((x) => typeof x === 'string' && x.trim() !== '').map((x) => x.trim());
}

function sharedDomainTags(a, b) {
  const doms = (r) => new Set((Array.isArray(r.fm?.tags) ? r.fm.tags : [])
    .map((t) => String(t)).filter((t) => t.startsWith('domain/')));
  return [...doms(a)].filter((t) => doms(b).has(t));
}

// ---------- --fix:确定性修复(§4;语义级永远只提案) ----------

async function applyFix(rec, ctx, fixed) {
  const fx = rec.fixCtx;
  if (!fx) return;
  let fm = rec.fm;
  let lines = rec.body.split('\n');
  let fmChanged = false;
  let bodyChanged = false;
  const fixes = [];

  if (fm !== null) {
    // ---- C5:N4 分治——非综合类 sources 禁止(确定性删除)----
    if (fm.sources !== undefined && !SYNTH_TYPES.has(rec.type)) {
      delete fm.sources;
      fmChanged = true;
      fixes.push({ rule: 'C5', action: '删除非综合类页禁止的 sources 字段(N4 分治)' });
    }

    // ---- C1:补占位(仅 §4 白名单字段)----
    for (const f of fx.c1Missing) {
      if (!C1_FILLABLE.has(f)) continue; // converter 等 → 提案,不补
      fm[f] = placeholderFor(f, rec);
      fmChanged = true;
      fixes.push({ rule: 'C1', action: `补 frontmatter ${f}` });
    }
    // ---- C1:类型强转 ----
    for (const c of fx.coerce) {
      if (c.field === 'tags') fm.tags = [String(fm.tags)];
      if (c.field === 'sources_count') fm.sources_count = parseInt(fm.sources_count, 10);
      if (c.field === 'native_text') fm.native_text = fm.native_text === 'true';
      fmChanged = true;
      fixes.push({ rule: 'C1', action: `类型强转: ${c.action}` });
    }

    // ---- C2:摘要/Summary 内容迁 summary + 删 H2 区块(倒序删防位移)----
    for (const hit of [...fx.c2Hits].sort((a, b) => b.idx - a.idx)) {
      let end = lines.length;
      for (let i = hit.idx + 1; i < lines.length; i++) {
        if (isBigHeading(lines[i])) {
          end = i;
          break;
        }
      }
      const content = lines.slice(hit.idx + 1, end).map((l) => l.trim()).filter(Boolean).join('\n');
      lines.splice(hit.idx, end - hit.idx);
      bodyChanged = true;
      if (content) {
        fm.summary = fm.summary ? `${fm.summary}\n\n${content}` : content;
        fmChanged = true;
      }
      fixes.push({ rule: 'C2', action: `「${hit.title}」内容迁 summary 并删 H2 区块` });
    }

    // ---- C3:追加缺失的 source 必备节 H2(规范位置插入,保 C17 子序列)----
    if (rec.type === 'source') {
      const keys = new Set(h2KeysOf(lines.join('\n')));
      const missing3 = C3_REQUIRED.filter((k) => !keys.has(k));
      if (missing3.length) {
        // 从后往前插:先插规范序靠后的节,靠前的节才有锚点
        for (const k of [...missing3].reverse()) {
          const successors = C17_SOURCE_ORDER.slice(C17_SOURCE_ORDER.indexOf(k) + 1);
          let anchor = -1;
          for (let i = 0; i < lines.length; i++) {
            if (isBigHeading(lines[i])) {
              const kk = h2Key(lines[i]);
              if (kk && successors.includes(kk)) {
                anchor = i;
                break;
              }
            }
          }
          if (anchor === -1) {
            while (lines.length && lines[lines.length - 1].trim() === '') lines.pop();
            lines.push('', `## ${k}`, '');
          } else {
            lines.splice(anchor, 0, `## ${k}`, '');
          }
        }
        bodyChanged = true;
        fixes.push({ rule: 'C3', action: `追加缺失节占位 H2: ${missing3.join(' / ')}` });
      }
    }

    // ---- C15.4 / C8:引用行(均门控 C7 无 FAIL)----
    if (rec.type === 'analysis' && Array.isArray(fm.sources_used) && fx.c7FailCount === 0) {
      const citeIdx = lines.findIndex((l) => CITE_LINE_RE.test(l.trim()));
      const wanted = `> 引用:${usedStemsOf(fm.sources_used).map((s) => `[[${s}]]`).join(', ')}`;
      if (citeIdx === -1) {
        const trimmed = lines.join('\n').replace(/\s*$/, '');
        lines = ((trimmed ? `${trimmed}\n\n` : '') + wanted).split('\n');
        bodyChanged = true;
        fixes.push({ rule: 'C15.4', action: '按 sources_used 生成文末「> 引用:」行' });
      } else {
        const lineStems = wikilinkTargets(lines[citeIdx]);
        const usedStems = usedStemsOf(fm.sources_used);
        const differs = usedStems.some((s) => !lineStems.includes(s)) || lineStems.some((s) => !usedStems.includes(s));
        if (differs) {
          lines[citeIdx] = wanted;
          bodyChanged = true;
          fixes.push({ rule: 'C8', action: '重写「> 引用:」行对齐 sources_used Set' });
        }
      }
    }
  }

  // ---- C15.5:md 链接 → wikilink(最后做,基于最终 body;跳代码围栏)----
  const conv = convertMdLinks(lines.join('\n'), rec, ctx);
  if (conv.count > 0) {
    lines = conv.body.split('\n');
    bodyChanged = true;
    fixes.push({ rule: 'C15.5', action: `标准 markdown 链接 ×${conv.count} 转 [[wikilink]]` });
  }

  if (!fmChanged && !bodyChanged) return; // 该页无可确定性修复项 → 零写入

  const newBody = lines.join('\n');
  // fm 变更 → 全量重 dump(注释丢失,§4 接受);仅 body 变更 → 原 frontmatter 字节保留
  const newContent = fmChanged
    ? `---\n${yaml.dump(fm, { lineWidth: -1 })}---\n${newBody}`
    : rec.fmRaw + newBody;
  await fs.writeFile(rec.abs, newContent, 'utf8');
  for (const f of fixes) fixed.push({ rule: f.rule, file: rec.rel, action: f.action });
}

/** §4 C1 占位值(冻结):updated ← 当前 ISO;title ← H1 文本;description/summary ← "";tags ← docform/other + domain/other;sources_count ← 0 */
function placeholderFor(field, rec) {
  switch (field) {
    case 'updated':
      return nowIso();
    case 'title': {
      const m = rec.body.match(/^#\s+(.+?)\s*$/m);
      return m ? m[1].trim() : rec.stem;
    }
    case 'description':
    case 'summary':
      return '';
    case 'tags':
      return ['docform/other', 'domain/other'];
    case 'sources_count':
      return 0;
    default:
      return '';
  }
}

/** C15.5 转换:逐行替换(跳代码围栏;目标解析不到 knowledge 页不转) */
function convertMdLinks(body, rec, ctx) {
  let count = 0;
  let inFence = false;
  const out = body.split('\n').map((line) => {
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence;
      return line;
    }
    if (inFence) return line;
    return line.replace(MD_LINK_RE, (whole, bang, text, target) => {
      if (bang === '!') return whole;
      const stem = resolveMdTarget(target, rec, ctx);
      if (!stem) return whole;
      count++;
      const label = text.trim();
      return label === stem ? `[[${stem}]]` : `[[${stem}|${label}]]`;
    });
  });
  return { body: out.join('\n'), count };
}

// ---------- log **LintFix** 行(§4;插入语义与 scripts/query/append-log.js 同款,复制 ~40 行不动冻结脚本) ----------

function appendLintFixToLog(knowledgeDir, fixed) {
  const nFiles = new Set(fixed.map((f) => f.file)).size;
  const byRule = new Map();
  for (const f of fixed) byRule.set(f.rule, (byRule.get(f.rule) || 0) + 1);
  // 规则号自然排序(C1 < C2 < C8 < C15.5),保证 log 行确定性
  const parts = [...byRule.entries()]
    .sort((a, b) => (parseFloat(a[0].slice(1)) || 0) - (parseFloat(b[0].slice(1)) || 0) || a[0].localeCompare(b[0]))
    .map(([r, n]) => `${r}×${n}`);
  const line = `**LintFix**: ${nFiles} 个文件确定性修复(${parts.join(', ')})`;

  let existed = true;
  let content = '';
  try {
    content = readFileSync(path.join(knowledgeDir, 'log.md'), 'utf8');
  } catch {
    existed = false;
  }
  const lines = content.replace(/\r\n/g, '\n').split('\n');
  const today = nowIso().slice(0, 10); // UTC 日期,对齐 query / ingest append-log 口径

  let action;
  const sec = findLogSection(lines, today);
  if (sec) {
    appendIntoLogSection(lines, sec, line);
    action = 'appended';
  } else {
    insertNewLogSection(lines, today, line);
    action = existed ? 'new-section' : 'created';
  }
  writeFileSync(path.join(knowledgeDir, 'log.md'), lines.join('\n'), 'utf8');
  return { line, action };
}

/** 在 lines 中定位当天节:{ h2Idx, endIdx }(endIdx = 下一日期 H2 / `## 维护` / EOF 的最小上界) */
function findLogSection(lines, today) {
  let h2Idx = -1;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(LOG_DATE_H2_RE);
    if (m && m[1] === today) {
      h2Idx = i;
      break;
    }
  }
  if (h2Idx === -1) return null;
  let endIdx = lines.length;
  for (let i = h2Idx + 1; i < lines.length; i++) {
    if (LOG_DATE_H2_RE.test(lines[i]) || lines[i].trim() === '## 维护') {
      endIdx = i;
      break;
    }
  }
  return { h2Idx, endIdx };
}

/** 行追加到当天节末尾(`---` 水平线之前,保持节尾水平线语义) */
function appendIntoLogSection(lines, section, line) {
  const { h2Idx, endIdx } = section;
  let p = endIdx - 1;
  while (p > h2Idx && lines[p].trim() === '') p--;
  if (p === h2Idx) {
    lines.splice(h2Idx + 1, 0, '', line);
    return;
  }
  if (lines[p].trim() === '---') {
    // `---` 紧跟文本行会被 markdown 解析成 setext H2,必须隔开
    const prevBlank = p - 1 > h2Idx && lines[p - 1].trim() === '';
    lines.splice(p, 0, ...(prevBlank ? [line, ''] : ['', line, '']));
    return;
  }
  lines.splice(p + 1, 0, '', line);
}

/** 新日期节插入:latest-first(第一个更旧日期 H2 之前;fallback `## 维护` / EOF) */
function insertNewLogSection(lines, today, line) {
  let insertAt = -1;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(LOG_DATE_H2_RE);
    if (m && m[1] < today) {
      insertAt = i;
      break;
    }
  }
  if (insertAt === -1) {
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim() === '## 维护') {
        insertAt = i;
        break;
      }
    }
  }
  const block = [`## [${today}]`, '', line, ''];
  if (insertAt === -1 || insertAt >= lines.length) {
    while (lines.length && lines[lines.length - 1].trim() === '') lines.pop();
    lines.push(...block);
    return;
  }
  if (insertAt > 0 && lines[insertAt - 1].trim() !== '' && lines[insertAt - 1].trim() !== '---') {
    block.unshift('');
  }
  lines.splice(insertAt, 0, ...block);
}

// ---------- 文本模式报告(stdout;**LintProposal** 提案行见 §0.1 / §4) ----------

function printTextReport(report, opts) {
  console.log(`[lint] project=${opts.project}`);
  console.log(`[lint] pages_scanned=${report.pages_scanned} reserved_skipped=${report.reserved_skipped}`);
  for (const f of report.fails) console.log(`FAIL [${f.rule}] ${f.file} — ${f.detail}`);
  for (const w of report.warns) console.log(`WARN [${w.rule}] ${w.file} — ${w.detail}`);
  for (const p of report.proposals) console.log(`**LintProposal**: [${p.kind}] ${p.file} — ${p.detail}`);
  // 语义级 fail/warn 同步出提案行(--fix 也不修,§0.1 分流)
  for (const f of report.fails) {
    if (f.rule === 'C1' && /缺少必填字段 (converter|converted_path|source_file|answer_to|sources_used|resource)/.test(f.detail)) {
      console.log(`**LintProposal**: [C1] ${f.file} — ${f.detail}(值语义未知,请人工补)`);
    } else if (SEMANTIC_FAIL_RULES.has(f.rule)) {
      console.log(`**LintProposal**: [${f.rule}] ${f.file} — ${f.detail}`);
    }
  }
  for (const w of report.warns) {
    if (SEMANTIC_WARN_RULES.has(w.rule)) console.log(`**LintProposal**: [${w.rule}] ${w.file} — ${w.detail}`);
  }
  for (const f of report.fixed || []) console.log(`FIXED [${f.rule}] ${f.file} — ${f.action}`);
  for (const c of report.c20_free_sections || []) {
    console.log(`C20 自由追加节(自检,不 FAIL): ${c.file} → ${c.sections.join(', ')}`);
  }
  console.log(`[lint] stats: fail=${report.stats.fail} warn=${report.stats.warn} proposal=${report.stats.proposal} fixed=${report.stats.fixed}`);
  if (report.pages_scanned === 0) console.log('[lint] wiki 为空,先跑 /aeps-llm-wiki-init + ingest 再 lint');
}

// ---------- 入口(环境 / 用法错误 → exit 1,区别于 FAIL 的 exit 2) ----------

main().catch((err) => {
  console.error(`ERROR: ${err.message}`);
  process.exit(1);
});
