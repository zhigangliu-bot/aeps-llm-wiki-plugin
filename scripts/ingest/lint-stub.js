#!/usr/bin/env node
/**
 * lint-stub.js — M2.4 lint skill 预留 stub(M2.4 落地前的临时实现)
 *
 * 本脚本是 lint skill (M2.4 任务) 的接口占位。
 * v0.5.6 起(批次 3 修复 P2-5):本 stub 不再固定 fail=0/warn=0,落地两条最小规则:
 *   - R7.1 (WARN,已被 R7.4 取代): tags <5 WARN → v0.6.5 起并入 R7.4,数量越界直接 ERROR
 *   - R7.2 (ERROR): 扫所有知识页 frontmatter `updated` 字段是否符合 ISO 8601,不符合时 ERROR
 * v0.5.9 起:加一条 v0.5.9 强约束
 *   - C21 (WARN): source 页 `## 重点摘录` 之前缺自由追加节 → WARN
 *                (对齐 page-source.md v0.5.9 起占位骨架 ## 阅读路线)
 * v0.6.5 起(修复 issue #12):新增 3 条 ERROR 规则,堵住「5 层防御中 lint 层漏拦」的缺口:
 *   - R7.4 (ERROR): tags 数量 <5 或 >10(对齐 frontmatter.schema.json minItems:5 / maxItems:10;
 *                   取代 R7.1 的 <5 WARN——数量越界直接 FAIL,不再降级 WARN)
 *   - R7.5 (ERROR): stale_after 非 ISO 8601 datetime(纯日期如 "2027-09-09" 必报错,
 *                   错误信息附正确格式示例;对齐 frontmatter-spec.md §4.5.2 + §4.8)
 *   - R7.6 (ERROR): sources[] 元素非对象(如字符串 "[[slug]]" 必报错,
 *                   错误信息附对象写法示例;对齐 schema sources.items.type: object)
 *
 * SKILL.md 步骤 19 调 `node scripts/ingest/lint-stub.js --project <dir>` 解析输出。
 *
 * 接口契约(锁定):
 *   - 输入:--project <dir>  (必填)
 *   - 输出(stdout): JSON 形如:
 *       {
 *         "project": "<dir>",
 *         "linted":  <number>,     // 扫到的 knowledge/ 页数
 *         "fail":    <number>,     // R7.2 / R7.4 / R7.5 / R7.6 ERROR 总数
 *         "warn":    <number>,     // R7.3 + C21 WARN 总数
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
 *       2 - 有 fail(规则 R7.2 / R7.4 / R7.5 / R7.6 触发)或缺依赖
 *
 * 设计原则:
 *   - **不动 lint 真实实现**:M2.4 任务会替换本 stub 内容,但接口契约(stdin/stdout/exit)不变。
 *   - **不破坏 SKILL.md 步骤 19 编排**:本 stub 输出 JSON 含 `linted` / `fail` / `warn` 字段,SKILL.md
 *     可正常解析;后续 M2.4 实现只需保证字段含义一致。
 *   - **不引入新依赖**:仅用 node:fs / node:path / node:process / scripts/lib/*(iso8601 复用)。
 *
 * change history:
 *   - 0.6.6 (issue #21 fix, PR-C):新增 R7.4 字典前缀校验 —— 每条 tag 必须匹配
 *     ^(domain|layer|phase|docform|maturity|tec)/[a-z0-9][a-z0-9-]*$ (对齐
 *     frontmatter-spec.md §4.2.4 + tag-spec.md §1.4);违规 → ERROR(fail++);
 *     必填轴 docform/ + domain/ 各 ≥1 条(对齐 tag-spec.md §1.2);单值轴
 *     docform/ + maturity/ 不可重复(对齐 tag-spec.md §1.3);STUB_VERSION M2.4-stub → M2.5-stub
 *   - 0.6.5 (issue #12 fix):新增 R7.4 / R7.5 / R7.6 三条 ERROR 规则(tags 数量区间 /
 *     stale_after ISO datetime / sources[] 元素对象类型),全部计入 fail → exit 2;
 *     原 R7.1(tags<5 WARN)被 R7.4 取代,不再产出 WARN。
 *     触发链:gen-page 空 skeleton(tags 空 / stale_after 空 / sources 字符串数组)→
 *     lint 不拦 → LLM 每页手工 Edit 6 字段 → ingest 无法一次成稿零 FAIL。
 *   - 0.6.3 (issue #6 fix):reserved filenames (index.md / log.md / overview.md / glossary.md)
 *     豁免 R7.1 / R7.2(对齐 frontmatter-spec.md §3.3 plugin 扩展 reserved 约定);
 *     新增 R7.3 (WARN):reserved filename 误含 frontmatter → 报告,不改文件。
 *     触发链:lint R7.1/R7.2 未豁免 reserved → ingest SKILL 步骤 19 FAIL →
 *     agent 反向给 reserved file 补 frontmatter 才过 → 污染 reserved file
 *     (本次同步修 aggregate-index.js 不再注入 frontmatter)。
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

const STUB_VERSION = 'M2.6-stub';
const MIN_TAGS_LENGTH = 5; // 对齐 doc/schema/frontmatter.schema.json tags minItems
// v0.6.5 (issue #12): R7.4 上限,对齐 frontmatter.schema.json tags maxItems
const MAX_TAGS_LENGTH = 10;
// v0.6.6 (issue #21, PR-C) R7.4 字典前缀正则 —— 对齐 frontmatter-spec.md §4.2.4
// 与 doc/template/tag-spec.md §1.4;6 轴字典权威位置为 tag-spec.md
const TAG_AXIS_RE_SRC = '(?:domain|layer|phase|docform|maturity|tec)';
const TAG_VALUE_RE = new RegExp(`^${TAG_AXIS_RE_SRC}/[a-z0-9][a-z0-9-]*$`);
// v0.6.6 (issue #21, PR-C) R7.4 必填轴 —— 对齐 tag-spec.md §1.2
const REQUIRED_TAG_AXES = ['docform', 'domain'];
// v0.6.6 (issue #21, PR-C) R7.4 单值轴 —— 对齐 tag-spec.md §1.3
const SINGLE_VALUE_TAG_AXES = new Set(['docform', 'maturity']);
// v0.5.9: C21 — source 页 ## 重点摘录 之前缺自由追加节 WARN
// (page-source.md v0.5.9 起把"自由追加节"从注释软指引升级为占位骨架 ## 阅读路线,
//  强制 LLM 读完源文件后先问『这篇有什么独特结构』再写正文)
const REQUIRED_BEFORE_KEY = '## 重点摘录';

// v0.6.3: reserved filenames 按 frontmatter-spec.md §3.3 plugin 扩展 + OKF §3.2 不携带 frontmatter。
// 豁免 R7.2 / R7.4 / R7.5 / R7.6(这些规则的前提是文件有 frontmatter,reserved file 没有所以无意义;
// R7.1 已于 v0.6.5 被 R7.4 取代,spec §3.3 的「R7.1 (tags<5)」表述待 spec 侧同步);
// 新增 R7.3 (WARN) 检测 reserved file 误含 frontmatter(报告不改文件,让用户 / 聚合脚本自决)。
const RESERVED_FILENAMES = new Set([
  'index.md',      // OKF §3.2
  'log.md',        // OKF §3.2
  'overview.md',   // plugin 扩展
  'glossary.md',   // plugin 扩展
]);

// ---- v0.6.5 (issue #12) R7.4 / R7.5 / R7.6 规则辅助 ----

/** 值的 YAML 类型名(错误信息用) */
function yamlTypeName(v) {
  if (v === null) return 'null';
  if (Array.isArray(v)) return 'array';
  return typeof v;
}

/** 值的简短预览(错误信息用),超长截断 */
function previewValue(v) {
  const s = typeof v === 'string' ? `"${v}"` : JSON.stringify(v);
  return s !== undefined && s.length > 80 ? `${s.slice(0, 77)}...` : s;
}

/**
 * R7.5:由非 datetime 值推导正确格式示例。
 * 值形如日期前缀(YYYY-MM-DD)→ 补全 T00:00:00Z;否则给通用格式占位。
 */
function isoDatetimeExample(value) {
  const m = typeof value === 'string' ? value.match(/^(\d{4}-\d{2}-\d{2})/) : null;
  return m ? `"${m[1]}T00:00:00Z"` : 'YYYY-MM-DDTHH:MM:SSZ';
}

/** R7.6:sources 正确写法提示(错误信息附示例) */
const SOURCES_FIX_HINT = '正确写法: - resource: "[[source-slug]]" + title: "来源标题"(详见 frontmatter-spec.md §4.4.1)';

/**
 * R7.4 (v0.6.5, issue #12):tags 数量必须在 [MIN_TAGS_LENGTH, MAX_TAGS_LENGTH] 区间。
 * 对齐 frontmatter.schema.json tags minItems:5 / maxItems:10。
 * 返回错误消息,合规返回 null。
 */
function checkTagsCount(tags) {
  const n = Array.isArray(tags) ? tags.length : 0;
  if (n >= MIN_TAGS_LENGTH && n <= MAX_TAGS_LENGTH) return null;
  return `R7.4 tags 数量 ${n} 条不合规,需 ≥${MIN_TAGS_LENGTH} 且 ≤${MAX_TAGS_LENGTH} 条(对齐 frontmatter.schema.json tags minItems/maxItems;必填轴 docform/ + domain/,详见 doc/template/tag-spec.md)`;
}

/**
 * R7.5 (v0.6.5, issue #12):stale_after 若存在,必须是 ISO 8601 datetime(带 T…Z / 时区偏移)。
 * 纯日期(如 "2027-09-09")不合规,错误信息附正确格式示例。
 * stale_after 是 OPTIONAL 字段,缺失 / null 不触发;空串触发。
 * 返回错误消息,合规(或缺省)返回 null。
 */
function checkStaleAfter(value) {
  if (value === undefined || value === null) return null;
  if (isIso8601(value)) return null;
  return `R7.5 stale_after 不是 ISO 8601 datetime: ${previewValue(value)}(纯日期不合规;正确示例: ${isoDatetimeExample(value)},格式 YYYY-MM-DDTHH:MM:SSZ;详见 frontmatter-spec.md §4.5.2)`;
}

/**
 * R7.6 (v0.6.5, issue #12):sources 若存在,必须是对象数组,每个元素是 {resource, ...} 对象。
 * 常见误写:LLM 把 sources 写成 ["[[slug]]"] 字符串数组(占位符没被替换 / 手写贪方便)。
 * 只查元素类型,不查 resource 必填(那是 schema required 的通道)。
 * 返回错误消息数组(可能多条),合规(或缺省)返回 []。
 */
function checkSourcesElements(value) {
  if (value === undefined || value === null) return [];
  const errs = [];
  if (!Array.isArray(value)) {
    errs.push(`R7.6 sources 应为对象数组,当前为 ${yamlTypeName(value)} ${previewValue(value)}(${SOURCES_FIX_HINT})`);
    return errs;
  }
  value.forEach((el, i) => {
    if (typeof el !== 'object' || el === null || Array.isArray(el)) {
      errs.push(`R7.6 sources[${i}] 应为 {resource, ...} 对象,当前为 ${yamlTypeName(el)} ${previewValue(el)}(${SOURCES_FIX_HINT})`);
    }
  });
  return errs;
}

// ---- v0.6.7 (issues #34/#35/#36) Obsidian 1.12.7 兼容规则 ----
// 注意编号冲突:issue 建议的 R7.5-R7.8 已被 stale_after/sources 占用,这里顺延为 R7.7-R7.10:
//   R7.7 (#35 方案B) aliases 数组重复项 → ERROR
//   R7.8 (#35 方案B) aliases 项被 [[...]] 或成对引号包裹 → ERROR
//   R7.9 (#34 方案C) frontmatter title 不在 aliases 数组 → ERROR(aliases 缺失时跳过,schema OPTIONAL)
//   R7.10 (#36 方案B) 正文 wikilink 左段不匹配任何 .md basename → WARN

/**
 * R7.7/R7.8/R7.9 (v0.6.7):aliases 数组合规检查。
 * 返回错误消息数组(可能多条),合规(或缺省)返回 []。
 */
function checkAliases(fm) {
  const errs = [];
  const aliases = fm.aliases;
  if (!Array.isArray(aliases)) return errs; // OPTIONAL 字段,缺省不触发
  // R7.7 去重
  const seen = new Set();
  for (const a of aliases) {
    const key = typeof a === 'string' ? a : JSON.stringify(a);
    if (seen.has(key)) {
      errs.push(`R7.7 aliases 数组重复项: ${previewValue(a)}(Obsidian 容忍但掩盖流程 bug;gen-page.js v0.6.7 起 cleanAliases 已去重)`);
    }
    seen.add(key);
  }
  // R7.8 包裹检查
  for (const a of aliases) {
    if (typeof a !== 'string') continue;
    if (/^\[\[.*\]\]$/.test(a.trim())) {
      errs.push(`R7.8 aliases 项不允许 wikilink 语法包裹: ${previewValue(a)}(剥掉 [[ ]] 写纯字符串)`);
    } else if ((/^".*"$/).test(a.trim()) || (/^'.*'$/).test(a.trim())) {
      errs.push(`R7.8 aliases 项含字面外层引号: ${previewValue(a)}(YAML 引号应是语法不是内容;剥掉后写纯字符串)`);
    }
  }
  // R7.9 title ∈ aliases(只查同时有 title 与 aliases 的页)
  if (typeof fm.title === 'string' && fm.title && !aliases.includes(fm.title)) {
    errs.push(`R7.9 frontmatter title 不在 aliases 数组中: ${previewValue(fm.title)}(title 必须作为 aliases 第一项;否则短标题 wikilink 在 Obsidian 1.12.7 跳空白页)`);
  }
  return errs;
}

/**
 * R7.10 (v0.6.7, issue #36 方案B):正文 wikilink 左段必须匹配 vault 内某 .md basename。
 * Obsidian 1.12.7 resolver 只索引文件名 basename(不读 aliases),不匹配 → 跳空白页 + vault 根堆空白文件。
 * 带路径的 wikilink([[sources/foo]])只比对最后一段;带 # 子页锚点忽略。
 * 返回警告消息数组,合规返回 []。
 */
function checkWikilinkBasenames(body, basenameSet, relPath) {
  const warns = [];
  const seen = new Set();
  const re = /\[\[([^\]#|]+)(?:#[^\]#|]*)?(?:\|[^\]]*)?\]\]/g;
  let m;
  while ((m = re.exec(body || '')) !== null) {
    const linkpath = m[1].trim().split('/').pop().replace(/\.md$/, '');
    if (!linkpath || seen.has(linkpath)) continue;
    seen.add(linkpath);
    if (!basenameSet.has(linkpath)) {
      warns.push(`${relPath}: R7.10 wikilink [[${m[1].trim()}]] 左段不匹配任何 .md basename(Obsidian 1.12.7 resolver 只认文件名,不读 aliases;点击会创建空白页;wikilink 文本必须用文件名形式)`);
    }
  }
  return warns;
}

/**
 * R7.4 (v0.6.6, issue #21, PR-C) 字典前缀 / 必填轴 / 单值轴校验。
 * 对齐 doc/schema/frontmatter-spec.md §4.2.4 + doc/template/tag-spec.md §1.2 / §1.3 / §1.4:
 *   - (a) 每条 tag 必须匹配 ^(domain|layer|phase|docform|maturity|tec)/[a-z0-9][a-z0-9-]*$
 *   - (b) 必填轴 docform/ + domain/ 各 ≥1 条
 *   - (c) 单值轴 docform/ + maturity/ 不可重复
 * 返回错误消息数组(可能多条),合规(或缺省)返回 []。
 */
function checkR74TagsDictPrefix(tags) {
  if (!Array.isArray(tags)) return [];
  const errs = [];
  // (a) 每条 tag 前缀正则
  for (const t of tags) {
    if (typeof t !== 'string' || !TAG_VALUE_RE.test(t)) {
      const v = previewValue(t);
      errs.push(`R7.4 tag 字典前缀校验失败: ${v} 不匹配 ^${TAG_AXIS_RE_SRC}/[a-z0-9][a-z0-9-]*$ (spec §4.2.4;6 轴字典见 doc/template/tag-spec.md §1.4)`);
    }
  }
  // (b) 必填轴(docform + domain)
  for (const axis of REQUIRED_TAG_AXES) {
    const has = tags.some((t) => typeof t === 'string' && t.startsWith(`${axis}/`));
    if (!has) {
      errs.push(`R7.4 必填轴缺失: 至少需要 1 条 '${axis}/...' tag (tag-spec.md §1.2;domain 是文档主题最基础坐标,缺失会让检索退化为「扫全表」)`);
    }
  }
  // (c) 单值轴(docform + maturity)
  for (const axis of SINGLE_VALUE_TAG_AXES) {
    const count = tags.filter((t) => typeof t === 'string' && t.startsWith(`${axis}/`)).length;
    if (count > 1) {
      errs.push(`R7.4 单值轴重复: '${axis}/' 出现 ${count} 次,最多 1 条 (tag-spec.md §1.3)`);
    }
  }
  return errs;
}

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

  // v0.6.7 (issue #36) R7.10:全 vault .md basename 集合(去 .md,reserved 文件也入集 —— index/glossary 等可被 wikilink)
  const basenameSet = new Set(pages.map((p) => p.relPath.split('/').pop().replace(/\.md$/, '')));

  for (const p of pages) {
    // v0.6.3: reserved filenames 走专属 R7.3 检查,跳过 R7.1 / R7.2(对齐 frontmatter-spec.md §3.3)
    const basename = p.relPath.split('/').pop();
    if (RESERVED_FILENAMES.has(basename)) {
      if (p.fm && Object.keys(p.fm).length > 0) {
        const templateName = basename.replace(/\.md$/, '');
        const msg = `R7.3 reserved filename 不应携带 frontmatter(按 frontmatter-spec.md §3.3;参考 doc/template/page-${templateName}.md 模板);当前含 ${Object.keys(p.fm).length} 个字段`;
        if (!warningsByFile[p.relPath]) warningsByFile[p.relPath] = [];
        warningsByFile[p.relPath].push(msg);
        flatWarnings.push(`${p.relPath}: ${msg}`);
      }
      // C21 在 reserved file 上天然不触发(fm.type 不是 'source'),无需额外 continue 标记
      continue;
    }

    const tags = Array.isArray(p.fm.tags) ? p.fm.tags : [];
    const updated = p.fm.updated;

    // R7.2: updated 不符合 ISO 8601 → ERROR(updated 字段不存在也算 ERROR)
    if (!updated || !isIso8601(updated)) {
      const msg = `updated 字段不符合 ISO 8601: ${updated === undefined || updated === null ? '(missing)' : String(updated)}`;
      if (!errorsByFile[p.relPath]) errorsByFile[p.relPath] = [];
      errorsByFile[p.relPath].push(msg);
      flatErrors.push(`${p.relPath}: ${msg}`);
    }

    // R7.4 (v0.6.5, issue #12): tags 数量 <5 或 >10 → ERROR(取代原 R7.1 的 <5 WARN;
    // 对齐 SKILL.md 步骤 19「FAIL 必须修复后才算 ingest 完成」)
    const r74 = checkTagsCount(tags);
    if (r74) {
      if (!errorsByFile[p.relPath]) errorsByFile[p.relPath] = [];
      errorsByFile[p.relPath].push(r74);
      flatErrors.push(`${p.relPath}: ${r74}`);
    }

    // R7.4 (v0.6.6, issue #21, PR-C) 字典前缀 / 必填轴 / 单值轴校验
    // 对齐 frontmatter-spec.md §4.2.4 + doc/template/tag-spec.md §1.2 / §1.3 / §1.4
    for (const msg of checkR74TagsDictPrefix(tags)) {
      if (!errorsByFile[p.relPath]) errorsByFile[p.relPath] = [];
      errorsByFile[p.relPath].push(msg);
      flatErrors.push(`${p.relPath}: ${msg}`);
    }

    // R7.5 (v0.6.5, issue #12): stale_after 非 ISO 8601 datetime → ERROR(纯 date 必报错)
    const r75 = checkStaleAfter(p.fm.stale_after);
    if (r75) {
      if (!errorsByFile[p.relPath]) errorsByFile[p.relPath] = [];
      errorsByFile[p.relPath].push(r75);
      flatErrors.push(`${p.relPath}: ${r75}`);
    }

    // R7.6 (v0.6.5, issue #12): sources[] 元素非对象 → ERROR(报错信息带正确写法示例)
    for (const msg of checkSourcesElements(p.fm.sources)) {
      if (!errorsByFile[p.relPath]) errorsByFile[p.relPath] = [];
      errorsByFile[p.relPath].push(msg);
      flatErrors.push(`${p.relPath}: ${msg}`);
    }

    // v0.6.7 (issues #34/#35): R7.7 重复 / R7.8 包裹 / R7.9 title∈aliases → ERROR
    for (const msg of checkAliases(p.fm)) {
      if (!errorsByFile[p.relPath]) errorsByFile[p.relPath] = [];
      errorsByFile[p.relPath].push(msg);
      flatErrors.push(`${p.relPath}: ${msg}`);
    }

    // v0.6.7 (issue #36): R7.10 正文 wikilink 左段须匹配某 .md basename → WARN
    for (const msg of checkWikilinkBasenames(p.body, basenameSet, p.relPath)) {
      if (!warningsByFile[p.relPath]) warningsByFile[p.relPath] = [];
      warningsByFile[p.relPath].push(msg);
      flatWarnings.push(msg);
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
