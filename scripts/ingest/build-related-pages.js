#!/usr/bin/env node
/**
 * build-related-pages.js — 双向反链生成
 *
 * Usage:
 *   node scripts/ingest/build-related-pages.js --project <dir> --batch <batch.json> [--apply] [--json]
 *
 * 双向反链规则(对齐 implement-ingest.md §1.1 + frontmatter-spec.md):
 *   source 页 → 写 `## 相关页面(Related Pages)` 区块
 *     - 按 ### Entities / ### Concepts 分组 wikilink
 *     - 某组空 → 省子标题;全空 → 省整节
 *   entity/concept 页 → 反向追加 `## 来源资料` 节
 *     - 按 source title 排序 wikilink
 *     - 无 source 引用 → 省整节
 *
 * 反链判定:扫 entity/concept 页 frontmatter `sources[].resource` 字段,匹配 source 页的 `resource`
 *   (或 absolute path),不解析正文 wikilink (避免循环)
 *
 * v0.5.6 起(批次 2 R3,修复 P1-5):语义从"完全重建"改为"追加 + 保留"。
 *   - 区块不存在 → 新建,只追加本次确认的反链(去重)
 *   - 区块已存在 → **保留** 区块下所有现有条目(含人工写的),在末尾追加本次确认的反链(去重)
 *   - 冲突条目(同 wikilink)→ 保留人工条目(可能含更详细别名/批注),WARN `duplicate, kept manual entry`
 *   - 若需完全重建 → 手工删除 `## 相关页面(...)` 区块后再跑
 *
 * v0.6.4: P0-#6 / P0-#3 — `resolveSourceByResource` 接受 5 种 resource 形态:
 *   1. `./raw/{subdir}/{file}` 原始 raw 路径(source.resource 标准形态)
 *   2. `knowledge/sources/{slug}.md` 绝对相对路径
 *   3. `[[sources/{slug}]]` / `[[sources/{slug}.md]]` Obsidian wikilink
 *   4. `sources/{slug}` / `sources/{slug}.md` 短路径
 *   5. `{slug}` / `{slug}.md` 裸 slug
 *   P2-#9 — `renderRelatedBlock` / `renderSourcesBlock` 不再向正文渲染 AI 风指示性话
 *   (RELATED_DESC / SOURCES_DESC),只保留 H2 + ### 子条目 + wikilink。
 *
 * Exit codes:
 *   0 - 成功
 *   1 - 参数错
 *   2 - 写盘失败,或 entity/concept 页 sources 字段类型不符(v0.6.5 起 ERROR)
 *
 * v0.6.5 (issue #12 / #17 校验侧): sources 字段类型不符从 WARN 升级为 ERROR exit 2。
 *   - 类型不符 = `sources` 存在但不是数组,或数组元素不是 {resource, ...} 对象
 *     (常见误写:LLM 把 sources 写成 ["[[slug]]"] 字符串数组)
 *   - 对齐 SKILL.md 步骤 19「FAIL 必须修复后才算 ingest 完成」:类型不符页跳过反链写盘,
 *     修复后重跑;同工程其他合规页的反链写入不受影响
 *   - 其余 ajv 校验失败(缺必填字段等)仍走 WARN + 跳过,不改变 v0.6.4 行为
 */

import { promises as fs, accessSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { requireDeps } from '../lib/preflight.js';
// 批次 3 P1-6: inline preflight 先跑;缺包 → throw 含精确 npm install 命令
await requireDeps({ 'js-yaml': 'js-yaml', ajv: 'ajv' });
// 动态 import:必须在 requireDeps 之后,否则 ESM 静态解析先抛 ERR_MODULE_NOT_FOUND
const yaml = (await import('js-yaml')).default;
const Ajv = (await import('ajv')).default;

// ---- ajv 校验 (对齐 frontmatter.schema.json) ----
// 失败语义(对齐 SKILL.md §失败语义):
//   - ajv 加载 schema 失败 → process.exit(2)
//   - ajv 校验 entity/concept frontmatter 失败 → stderr WARN + 跳过该页(反链不写)
//
// SCHEMA_PATH 解析顺序(v0.5.8 起,design.md D2):
//   1. --schema-path <absolute>(CLI 显式覆盖,最高优先级)
//   2. process.env.WIKI_SCHEMA_PATH(env,可选)
//   3. <project>/doc/schema/frontmatter.schema.json(用户工程 v0.5.8 起标准路径)
//   4. <plugin-root>/doc/schema/frontmatter.schema.json(plugin 自检,plugin-root 由 D1 解析)
//
// project 解析顺序(design.md D2):
//   - --project <absolute> CLI > process.env.WIKI_PROJECT > process.cwd()
let ajvValidate = null;

function resolvePluginRoot(cliArg) {
  if (cliArg) return path.resolve(cliArg);
  if (process.env.CLAUDE_PLUGIN_ROOT) return path.resolve(process.env.CLAUDE_PLUGIN_ROOT);
  const candidate = path.resolve(import.meta.dirname, '..', '..', '.claude-plugin', 'plugin.json');
  try {
    accessSync(candidate);
    return path.resolve(import.meta.dirname, '..', '..');
  } catch {
    return null;
  }
}

function resolveProject(cliArg) {
  if (cliArg) return path.resolve(cliArg);
  if (process.env.WIKI_PROJECT) return path.resolve(process.env.WIKI_PROJECT);
  return path.resolve(process.cwd());
}

function resolveSchemaCandidates(args) {
  if (args.schemaPath) return [path.resolve(args.schemaPath)];
  if (process.env.WIKI_SCHEMA_PATH) return [path.resolve(process.env.WIKI_SCHEMA_PATH)];
  const project = resolveProject(args.project);
  const pluginRoot = resolvePluginRoot(args.pluginRoot);
  // ponytail: v0.5.8 起去掉 <project>/schema/ 候选(用户工程根不再有 schema/,只在 doc/schema/)。
  const candidates = [
    path.join(project, 'doc', 'schema', 'frontmatter.schema.json'),
  ];
  if (pluginRoot) {
    candidates.push(path.join(pluginRoot, 'doc', 'schema', 'frontmatter.schema.json'));
  }
  return candidates;
}

async function pickSchemaPath(candidates) {
  for (const p of candidates) {
    try {
      await fs.access(p);
      return p;
    } catch {
      // continue
    }
  }
  return null;
}

async function loadValidator() {
  if (ajvValidate) return ajvValidate;
  const args = currentArgs || {};
  const candidates = resolveSchemaCandidates(args);
  const SCHEMA_PATH = await pickSchemaPath(candidates);
  if (!SCHEMA_PATH) {
    console.error(`ERROR: 无法定位 frontmatter schema;候选路径:`);
    for (const p of candidates) console.error(`  - ${p}`);
    console.error(`解决:用 --schema-path <absolute> 显式指定;或 --project 指向含 doc/schema/ 的用户工程;或 --plugin-root 指向 plugin 仓根`);
    process.exit(2);
  }
  let schema;
  try {
    const txt = await fs.readFile(SCHEMA_PATH, 'utf8');
    schema = JSON.parse(txt);
  } catch (e) {
    console.error(`ERROR: 无法加载 frontmatter schema ${SCHEMA_PATH}: ${e.message}`);
    process.exit(2);
  }
  try {
    // ajv 8 默认仅支持 draft-07;本 schema 标 draft 2020-12 但实际未用 draft 关键字,
    // 去掉 $schema 走默认 meta 即可 compile。
    delete schema.$schema;
    const ajv = new Ajv({ allErrors: true, strict: false });
    ajvValidate = ajv.compile(schema);
    return ajvValidate;
  } catch (e) {
    console.error(`ERROR: ajv 编译 schema 失败: ${e.message}`);
    process.exit(2);
  }
}

// 模块级 args 缓存(loadValidator 在 scanEntityConcept 内异步调用,需要拿到 CLI 解析结果)
let currentArgs = null;

// 实体 / 概念子目录列表(对齐 doc/schema/schema.md §1.1: 18 叶子 1:1 绑死)
// entity.concept. 子目录 7 个;concept.* 子目录 7 个
const ENTITY_DIRS = ['person', 'organization', 'project', 'product', 'event', 'place', 'other'];
const CONCEPT_DIRS = ['theory', 'method', 'field', 'phenomenon', 'standard', 'term', 'other'];

const RELATED_H2 = '## 相关页面(Related Pages,由 ingest 自动生成)';
// 同时识别"用户手工标题"——只匹配 `## 相关页面`,允许后缀自定义。
// 用于 P1-5 修复:手工写过 `## 相关页面(我手工补的)` 也走追加保留。
const RELATED_H2_PREFIX = '## 相关页面';
const RELATED_ENTITIES_H3 = '### Entities';
const RELATED_CONCEPTS_H3 = '### Concepts';
const SOURCES_H2 = '## 来源资料(由 ingest 自动生成)';
// 同样兼容用户手工 `## 来源资料` 标题
const SOURCES_H2_PREFIX = '## 来源资料';

// 反链区块说明文字常量(对齐 page-source.md L111 / page-entity-*.md L55):
// v0.5.6 起改为"追加 + 保留"语义;人工补的条目保留,WARN 重复时让位给人工条目。
// v0.6.4 (issue #9 fix): 不再渲染到正文 —— 「追加模式 / 重建说明」是 SKILL.md / 设计文档
// 应有的元信息,wiki 正文里出现 AI 风指示性话违反用户偏好。删除 RELATED_DESC / SOURCES_DESC
// 实际渲染调用;常量保留作 schema 占位/未来 lint 引用。
// eslint-disable-next-line no-unused-vars
const RELATED_DESC_PLACEHOLDER = '本节由 `/aeps-llm-wiki-ingest` 自动追加(追加 + 保留语义;详见 SKILL.md)。';
// eslint-disable-next-line no-unused-vars
const SOURCES_DESC_PLACEHOLDER = '本节由 `/aeps-llm-wiki-ingest` 自动追加(追加 + 保留语义;详见 SKILL.md)。';

// ---- frontmatter 解析 ----
// 返回 fm(对象,用于 ajv 校验等)+ fmRaw(原文 '---...---\n',写盘直接拼回,避免 yaml.dump 重写丢引号)
function parseFrontmatter(mdText) {
  const m = mdText.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  if (!m) return { fm: {}, fmRaw: '', body: mdText };
  let fm = {};
  try { fm = yaml.load(m[1]) || {}; } catch { fm = {}; }
  // 保留原 fm 块文本 + 收尾 '\n';字段顺序/注释行/引号风格原样保留。
  const fmRaw = `---\n${m[1]}\n---\n`;
  return { fm, fmRaw, body: m[2] };
}

// ---- v0.6.5 (issue #12 / #17): sources 字段类型检测 ----

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

// 修复指引(对齐 SKILL.md 步骤 19「FAIL 必须修复后才算 ingest 完成」)
const SOURCES_FIX_HINT = '正确写法: - resource: "[[source-slug]]" + title: "来源标题"(详见 frontmatter-spec.md §4.4.1;SKILL.md 步骤 19:FAIL 必须修复后才算 ingest 完成,修复后重跑 build-related-pages)';

/**
 * sources 字段类型检测(对齐 frontmatter.schema.json sources.type: array + items.type: object)。
 * 只查类型;元素缺 resource 必填仍走 ajv required 的 WARN 通道,不在此升级。
 * 返回错误消息数组(可能多条);字段缺省 / null 返回 [](OPTIONAL 字段不触发)。
 */
function sourcesTypeErrors(rawSources) {
  if (rawSources === undefined || rawSources === null) return [];
  const errs = [];
  if (!Array.isArray(rawSources)) {
    errs.push(`sources 字段类型不符:应为对象数组,当前为 ${yamlTypeName(rawSources)} ${previewValue(rawSources)};${SOURCES_FIX_HINT}`);
    return errs;
  }
  rawSources.forEach((el, i) => {
    if (typeof el !== 'object' || el === null || Array.isArray(el)) {
      errs.push(`sources 字段类型不符:sources[${i}] 应为 {resource, ...} 对象,当前为 ${yamlTypeName(el)} ${previewValue(el)};${SOURCES_FIX_HINT}`);
    }
  });
  return errs;
}

// 渲染 frontmatter block:issue #37 fix,改用 parse 时保留的原文 fmRaw 直接返回;
// 不再 yaml.dump 重写(forceQuotes:false 会丢字符串双引号,违反 frontmatter-spec.md §4.1 +
// issue #23 强约束)。fm 形参名保留但仅用于提示契约,实际不读。
function renderFrontmatterBlock(_fm, fmRaw = '') {
  return fmRaw;
}

// 把 path 标准化(正斜杠)
function norm(p) {
  return p.replace(/\\/g, '/');
}

// 把 ./raw/06_功能安全/foo.pdf 这种 resource 路径转成 slug
function resourceToSlug(resource) {
  if (!resource) return null;
  let r = norm(resource).replace(/^\.\//, '');
  // 期望形如 raw/{subdir}/{file}
  const m = r.match(/^raw\/[^/]+\/(.+)$/);
  if (m) return m[1].replace(/\.md$/, '');
  // 兜底:若以 .md 结尾,去掉
  if (r.endsWith('.md')) return path.basename(r, '.md');
  return null;
}

// 从 file.path (inbox/foo.pdf) 提取 slug = foo
function inboxToSlug(filePath) {
  const base = path.basename(filePath);
  return base.replace(/\.[^.]+$/, '');
}

async function readJson(p) {
  const txt = await fs.readFile(p, 'utf8');
  return JSON.parse(txt);
}

async function listMarkdown(dir) {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    return entries.filter(e => e.isFile() && e.name.endsWith('.md') && !e.name.startsWith('.')).map(e => path.join(dir, e.name));
  } catch {
    return [];
  }
}

// 扫所有 source 页
async function scanSources(knowledgeDir) {
  const sourcesDir = path.join(knowledgeDir, 'sources');
  const files = await listMarkdown(sourcesDir);
  const out = [];
  for (const f of files) {
    const txt = await fs.readFile(f, 'utf8');
    const { fm, fmRaw, body } = parseFrontmatter(txt);
    if (fm.type !== 'source') continue;
    out.push({
      file: f,
      relPath: norm(path.relative(knowledgeDir, f)),
      slug: path.basename(f, '.md'),
      title: fm.title || path.basename(f, '.md'),
      resource: norm(fm.resource || ''),
      fm,
      fmRaw,
      body,
    });
  }
  return out;
}

// 扫 entity/concept 页
// 失败语义(对齐 SKILL.md §失败语义):
//   - ajv 校验失败 → stderr WARN + 跳过该页(反链不写)
//   - sources 字段类型不符 → stderr ERROR(v0.6.5 起)+ 跳过该页;ERROR 计入 fail,整体 exit 2
async function scanEntityConcept(knowledgeDir) {
  const validate = await loadValidator();
  const out = [];
  // entities/*/*
  for (const sub of ENTITY_DIRS) {
    const dir = path.join(knowledgeDir, 'entities', sub);
    for (const f of await listMarkdown(dir)) {
      const txt = await fs.readFile(f, 'utf8');
      const { fm, fmRaw, body } = parseFrontmatter(txt);
      if (!fm.type || !fm.type.startsWith('entity.')) continue;
      const invalid = !validate(fm);
      // v0.6.5 (issue #12/#17): sources 字段类型不符检测 → ERROR 通道(stderr ERROR + exit 2)
      const srcTypeErrs = sourcesTypeErrors(fm.sources);
      if (invalid) {
        // 类型不符已走 ERROR 通道,这里把 /sources 的 type 错从 WARN 列表剔除,避免同一问题双报
        const ajvErrs = (validate.errors || []).filter((e) =>
          !(srcTypeErrs.length > 0 && String(e.instancePath || '').startsWith('/sources') && e.keyword === 'type'));
        if (ajvErrs.length) {
          const errs = ajvErrs.map(e => `${e.instancePath || '/'} ${e.message}`).join('; ');
          console.error(`WARN: ${f}: ${errs}`);
        }
      }
      out.push({
        file: f,
        relPath: norm(path.relative(knowledgeDir, f)),
        slug: path.basename(f, '.md'),
        title: fm.title || path.basename(f, '.md'),
        type: fm.type,
        sources: Array.isArray(fm.sources) ? fm.sources : [],
        fm,
        fmRaw,
        body,
        invalid,
        srcTypeErrs,
      });
    }
  }
  for (const sub of CONCEPT_DIRS) {
    const dir = path.join(knowledgeDir, 'concepts', sub);
    for (const f of await listMarkdown(dir)) {
      const txt = await fs.readFile(f, 'utf8');
      const { fm, fmRaw, body } = parseFrontmatter(txt);
      if (!fm.type || !fm.type.startsWith('concept.')) continue;
      const invalid = !validate(fm);
      // v0.6.5 (issue #12/#17): sources 字段类型不符检测 → ERROR 通道(stderr ERROR + exit 2)
      const srcTypeErrs = sourcesTypeErrors(fm.sources);
      if (invalid) {
        // 类型不符已走 ERROR 通道,这里把 /sources 的 type 错从 WARN 列表剔除,避免同一问题双报
        const ajvErrs = (validate.errors || []).filter((e) =>
          !(srcTypeErrs.length > 0 && String(e.instancePath || '').startsWith('/sources') && e.keyword === 'type'));
        if (ajvErrs.length) {
          const errs = ajvErrs.map(e => `${e.instancePath || '/'} ${e.message}`).join('; ');
          console.error(`WARN: ${f}: ${errs}`);
        }
      }
      out.push({
        file: f,
        relPath: norm(path.relative(knowledgeDir, f)),
        slug: path.basename(f, '.md'),
        title: fm.title || path.basename(f, '.md'),
        type: fm.type,
        sources: Array.isArray(fm.sources) ? fm.sources : [],
        fm,
        fmRaw,
        body,
        invalid,
        srcTypeErrs,
      });
    }
  }
  return out;
}

// ---- 区块渲染 ----
// v0.6.4 (issue #9 fix): 删除 AI 风指示性话(desc 字段),只保留 H2 标题 + ### 子条目 + wikilink。
function renderRelatedBlock(entities, concepts) {
  if (!entities.length && !concepts.length) return null;
  const lines = [RELATED_H2, ''];
  if (entities.length) {
    lines.push(RELATED_ENTITIES_H3, '');
    for (const e of entities.sort((a, b) => a.title.localeCompare(b.title))) {
      lines.push(`- [[${e.slug}]]`);
    }
    lines.push('');
  }
  if (concepts.length) {
    lines.push(RELATED_CONCEPTS_H3, '');
    for (const c of concepts.sort((a, b) => a.title.localeCompare(b.title))) {
      lines.push(`- [[${c.slug}]]`);
    }
    lines.push('');
  }
  return lines.join('\n');
}

function renderSourcesBlock(sourceRefs) {
  if (!sourceRefs.length) return null;
  const lines = [SOURCES_H2, ''];
  for (const s of sourceRefs.sort((a, b) => a.title.localeCompare(b.title))) {
    lines.push(`- [[${s.slug}]]`);
  }
  lines.push('');
  return lines.join('\n');
}

// ---- body 区块替换(追加 + 保留语义,v0.5.6 起 P1-5 修复) ----
/**
 * 在 body 中定位 H2 区块;返回 {start, end} (start 是 H2 行号,end 是下一个 ## 行号或文末)
 * 若不存在 → 返回 null
 *
 * h2Matcher: 精确字符串(如 RELATED_H2)或前缀函数(如 (line) => line.startsWith('## 相关页面'))
 */
function findH2Block(body, h2Matcher) {
  const lines = body.split('\n');
  let start = -1;
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (typeof h2Matcher === 'function' ? h2Matcher(trimmed) : trimmed === h2Matcher) {
      start = i;
      break;
    }
  }
  if (start < 0) return null;
  let end = lines.length;
  for (let j = start + 1; j < lines.length; j++) {
    if (/^##\s/.test(lines[j].trim())) {
      end = j;
      break;
    }
  }
  return { start, end };
}

/**
 * 提取 wikilink 条目(- [[xxx]] 或 - [[xxx|alias]] 或带行尾批注)的 slug 集合
 * 行尾可有任意文字(批注 / 标记),但不能紧接着再一个 wikilink
 */
function extractWikilinkSlugs(blockText) {
  const slugs = new Set();
  for (const line of blockText.split('\n')) {
    // 匹配 - 后跟 [[xxx]] 或 [[xxx|alias]],后面可有任意行尾文字
    const m = line.match(/^-\s+\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]/);
    if (m) slugs.add(m[1]);
  }
  return slugs;
}

// ponytail: v0.6.2 起,gen-page.js 步骤 7 / page-source.md L129-137 会在 ## 相关页面 区块
// 留占位行(【本节由 ... 自动生成 ...】 + 空 ### Entities/Concepts H3 + 【自动填充 ...】)。
// LLM 完稿后这些占位若不清掉,会留在正文中影响阅读。appendRelatedEntries 入口先剥掉,
// 然后再追加本次确认的 wikilink(去重)。占位识别严格:行首【行尾】 + 内容含"自动生成/自动填充"。
// 不误伤 LLM 自写的 [来源不足,需人工复核] 等。
const PLACEHOLDER_LINE_RE = /^【[^】]*(自动生成|自动填充)[^】]*】\s*$/;
const H3_LINE_RE = /^###\s+/;
const WIKILINK_LINE_RE = /^-\s+\[\[/;

// 从 H2 区块文本中剥掉:占位行 + 空 H3(下面没 wikilink)及其附属占位行
function stripPlaceholderLines(blockText) {
  const lines = blockText.split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const t = lines[i].trim();
    // 1) 占位行 → 直接丢
    if (PLACEHOLDER_LINE_RE.test(t)) {
      i++;
      continue;
    }
    // 2) H3 行(### Entities/Concepts 等) → 看后续是否空组
    if (H3_LINE_RE.test(t)) {
      // 收集 H3 后到下一个 H2/H3/文末 的内容
      const groupStart = out.length;
      out.push(lines[i]);
      i++;
      let hasWikilink = false;
      // 扫 H3 块直到下一个 H2/H3
      while (i < lines.length) {
        const lt = lines[i].trim();
        if (H3_LINE_RE.test(lt) || /^##\s/.test(lt)) break;
        if (PLACEHOLDER_LINE_RE.test(lt)) {
          // 占位行 → 丢,不进 out
          i++;
          continue;
        }
        if (WIKILINK_LINE_RE.test(lt)) {
          hasWikilink = true;
          out.push(lines[i]);
        } else {
          // 空行 / 其他文本(LLM 写的批注)
          out.push(lines[i]);
        }
        i++;
      }
      if (!hasWikilink) {
        // 空 H3 段:删掉 H3 及其下所有附属行(占位 + 空行 + 其他)
        out.splice(groupStart, out.length - groupStart);
      }
      continue;
    }
    out.push(lines[i]);
    i++;
  }
  // 折叠连续 ≥2 个空行为 1 个(保留块内单空行)
  const collapsed = [];
  let blankRun = 0;
  for (const l of out) {
    if (l.trim() === '') {
      blankRun++;
      if (blankRun <= 1) collapsed.push(l);
    } else {
      blankRun = 0;
      collapsed.push(l);
    }
  }
  return collapsed.join('\n');
}

/**
 * 对齐 H2 区块末尾:把给定的新 wikilink 条目按 entities/concepts(或 sources)顺序追加到现有区块,
 *   去重(wikilink 字符串)。
 * 返回 { newBlock, duplicates }:newBlock 是替换后的完整区块文本;
 *   duplicates 是与本次确认冲突的人工 wikilink 列表(已保留人工条目,WARN 用)。
 */
function appendRelatedEntries(existingBlockText, entities, concepts) {
  // ponytail: 先剥占位行 / 空 H3 段(v0.6.2,见上方 stripPlaceholderLines 注释)
  const cleaned = stripPlaceholderLines(existingBlockText);
  const before = extractWikilinkSlugs(cleaned);
  const newEntities = entities
    .filter((e) => !before.has(e.slug))
    .sort((a, b) => a.title.localeCompare(b.title));
  const newConcepts = concepts
    .filter((c) => !before.has(c.slug))
    .sort((a, b) => a.title.localeCompare(b.title));

  // 重复检测:本次确认的 wikilink 已存在 → 让位给人工(已保留在原 block)
  const duplicates = [];
  for (const e of entities) if (before.has(e.slug)) duplicates.push(e.slug);
  for (const c of concepts) if (before.has(c.slug)) duplicates.push(c.slug);

  const lines = cleaned.replace(/\s+$/, '').split('\n');
  // 末尾追加(只在有空组时考虑 ### 子标题的重复)
  if (newEntities.length) {
    const hasEntitiesH3 = lines.some((l) => l.trim() === RELATED_ENTITIES_H3);
    if (!hasEntitiesH3) {
      lines.push('', RELATED_ENTITIES_H3);
    }
    for (const e of newEntities) lines.push(`- [[${e.slug}]]`);
  }
  if (newConcepts.length) {
    const hasConceptsH3 = lines.some((l) => l.trim() === RELATED_CONCEPTS_H3);
    if (!hasConceptsH3) {
      lines.push('', RELATED_CONCEPTS_H3);
    }
    for (const c of newConcepts) lines.push(`- [[${c.slug}]]`);
  }
  return { newBlock: lines.join('\n') + '\n', duplicates };
}

function appendSourcesEntries(existingBlockText, sourceRefs) {
  const before = extractWikilinkSlugs(existingBlockText);
  const newRefs = sourceRefs
    .filter((s) => !before.has(s.slug))
    .sort((a, b) => a.title.localeCompare(b.title));
  const duplicates = sourceRefs.filter((s) => before.has(s.slug)).map((s) => s.slug);

  const lines = existingBlockText.replace(/\s+$/, '').split('\n');
  for (const s of newRefs) lines.push(`- [[${s.slug}]]`);
  return { newBlock: lines.join('\n') + '\n', duplicates };
}

/**
 * 在 body 中定位 H2 区块并替换 block 内容(从 start 到 end-1 行替换为 newBlock),
 * 保留 start+1 行以外的 H2(下一个 ## 仍保留)。
 */
function replaceH2Block(body, start, end, newBlock) {
  const lines = body.split('\n');
  const before = lines.slice(0, start);
  const after = lines.slice(end);
  // 确保 before 末尾空行、after 开头空行
  return [...before, newBlock, ...after].join('\n').replace(/\n{3,}/g, '\n\n');
}

/**
 * 在 body 中插入新块到 ## 维护说明 之前(且 ## 维护说明 之前补 `---` 水平线,对齐模板 L57)
 * 若 ## 维护说明 不存在 → 追加到文末
 */
function insertBeforeMaintain(body, block) {
  const lines = body.split('\n');
  const out = [];
  let inserted = false;
  for (const line of lines) {
    if (!inserted && line.trim().startsWith('## 维护说明')) {
      out.push(block);
      out.push('');
      out.push('---');
      out.push('');
      inserted = true;
    }
    out.push(line);
  }
  if (!inserted) {
    out.push('');
    out.push(block);
  }
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd() + '\n';
}

function parseArgs(argv) {
  const args = { project: null, batch: null, apply: false, json: false, pluginRoot: null, schemaPath: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--batch') args.batch = argv[++i];
    else if (a === '--apply') args.apply = true;
    else if (a === '--json') args.json = true;
    else if (a === '--plugin-root') args.pluginRoot = argv[++i];
    else if (a === '--schema-path') args.schemaPath = argv[++i];
  }
  if (!args.project || !args.batch) {
    console.error('ERROR: --project / --batch 必填');
    process.exit(1);
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  currentArgs = args;
  const project = path.resolve(args.project);
  const knowledgeDir = path.join(project, 'knowledge');
  const dryRun = !args.apply;

  const batch = await readJson(args.batch);

  // 1. 收集本 batch 的 source slug(由 init-batch 写入的 files[].path → inboxToSlug)
  const batchSourceSlugs = new Set(batch.files.map(f => inboxToSlug(f.path)).filter(Boolean));

  // 2. 扫所有 source / entity / concept 页
  const sources = await scanSources(knowledgeDir);
  const ecPages = await scanEntityConcept(knowledgeDir);

  // 3. 建立索引:source.resource → source 对象 (作为反链目标)
  // 也允许 batch 内未迁移的 source(以 resource 路径比对)
  const sourceByResource = new Map();
  const sourceBySlug = new Map();
  for (const s of sources) {
    if (s.resource) sourceByResource.set(s.resource, s);
    sourceBySlug.set(s.slug, s);
  }

  // 4. 计算 entity/concept → sources 反链映射
  //    通过 fm.sources[].resource 匹配
  //    资源可能是:
  //    - ./knowledge/sources/{slug}.md → 直接 slug
  //    - ./raw/{subdir}/{file} → 由 SKILL.md 抽取时建 entity/concept 时填此值, 反查 source.resource
  // v0.6.4 (issue #6 fix): resource 路径接受 5 种形态 —
  //   1. ./raw/{subdir}/{file}            → sourceByResource
  //   2. knowledge/sources/{slug}.md      → 提取 slug 后 sourceBySlug
  //   3. [[sources/{slug}]] / [[sources/{slug}.md]]  (Obsidian wikilink)
  //   4. sources/{slug} / sources/{slug}.md         (短路径,相对 knowledge/)
  //   5. {slug} / {slug}.md               (裸 slug,裸文件名)
  //   兜底:路径最后一段去 .md 后做 slug
  function resolveSourceByResource(rawResource) {
    if (!rawResource) return null;
    let r = norm(rawResource).trim();
    // 剥 Obsidian wikilink [[xxx]] 或 [[xxx|alias]]
    r = r.replace(/^\[\[/, '').replace(/\]\]$/, '').split('|')[0].trim();
    if (!r) return null;
    // 1. 完整 raw/ 路径(已是 source.resource 的标准形态)
    let m = sourceByResource.get(r);
    if (m) return m;
    // 2. knowledge/sources/{slug}.md
    m = r.match(/knowledge\/sources\/([^/]+?)(?:\.md)?$/);
    if (m && sourceBySlug.has(m[1])) return sourceBySlug.get(m[1]);
    // 3/4. sources/{slug}[.md] 或 ./sources/{slug}[.md]
    m = r.match(/(?:\.\/)?sources\/([^/]+?)(?:\.md)?$/);
    if (m && sourceBySlug.has(m[1])) return sourceBySlug.get(m[1]);
    // 5. 裸 slug / 裸 slug.md
    m = r.match(/^([^/]+?)(?:\.md)?$/);
    if (m && sourceBySlug.has(m[1])) return sourceBySlug.get(m[1]);
    return null;
  }

  const ecToSources = new Map(); // ec.relPath → [{ slug, title }]
  for (const ec of ecPages) {
    const refs = [];
    const seen = new Set();
    for (const src of ec.sources) {
      const matched = resolveSourceByResource(src.resource);
      if (matched && !seen.has(matched.slug)) {
        refs.push({ slug: matched.slug, title: matched.title });
        seen.add(matched.slug);
      }
    }
    if (refs.length) ecToSources.set(ec.relPath, refs);
  }

  // 5. 计算 source → entities / concepts 反向映射
  //    反查:扫所有 entity/concept,若其 sources 指向此 source → 加到此 source 的 entities/concepts
  const sourceToEc = new Map(); // source.slug → { entities:[], concepts:[] }
  for (const s of sources) {
    sourceToEc.set(s.slug, { entities: [], concepts: [] });
  }
  for (const ec of ecPages) {
    for (const src of ec.sources) {
      const matched = resolveSourceByResource(src.resource);
      if (!matched) continue;
      const bucket = sourceToEc.get(matched.slug);
      if (!bucket) continue;
      if (ec.type.startsWith('entity.')) bucket.entities.push({ slug: ec.slug, title: ec.title });
      else if (ec.type.startsWith('concept.')) bucket.concepts.push({ slug: ec.slug, title: ec.title });
    }
  }

  const writes = [];

  // P2-1 批次 3: 收集 warnings_by_file(供 lint stub 复用)
  // 扫所有 entity/concept 页,tags 长度 < 5 → WARN(对齐 frontmatter-spec.md §C17 + schema minItems)
  const warningsByFile = {};
  const flatWarnings = [];
  function pushWarning(relPath, msg) {
    if (!warningsByFile[relPath]) warningsByFile[relPath] = [];
    warningsByFile[relPath].push(msg);
    flatWarnings.push(`${relPath}: ${msg}`);
  }
  for (const ec of ecPages) {
    const tags = Array.isArray(ec.fm.tags) ? ec.fm.tags : [];
    if (tags.length < 5) {
      pushWarning(ec.relPath, `tags 仅 ${tags.length} 条,需 ≥5 条`);
    }
  }

  // v0.6.5 (issue #12 / #17): sources 字段类型不符 → ERROR(原 WARN 升级)
  // 对齐 SKILL.md 步骤 19「FAIL 必须修复后才算 ingest 完成」:类型不符说明该页 frontmatter
  // 未按 schema 写(常见:LLM 把 sources 写成 ["[[slug]]"] 字符串数组),反链无法安全计算,
  // 该页跳过写盘;修复后重跑本脚本。同工程其他合规页反链写入不受影响。
  const errorsByFile = {};
  const flatErrors = [];
  function pushError(relPath, msg) {
    if (!errorsByFile[relPath]) errorsByFile[relPath] = [];
    errorsByFile[relPath].push(msg);
    flatErrors.push(`${relPath}: ${msg}`);
    console.error(`ERROR: ${relPath}: ${msg}`);
  }
  for (const ec of ecPages) {
    for (const msg of ec.srcTypeErrs || []) pushError(ec.relPath, msg);
  }

  // 6. 追加 + 保留:source 页 ## 相关页面 区块
  //   - 不存在 → 新建标准 block(只在 ## 维护说明 前插入)
  //   - 已存在 → 解析现有 wikilink,在末尾追加本次确认的新反链(去重),保留人工条目
  for (const s of sources) {
    const { entities, concepts } = sourceToEc.get(s.slug) || { entities: [], concepts: [] };
    let newBody = s.body;
    let action;
    const existing = findH2Block(s.body, (l) => l === RELATED_H2 || l.startsWith(RELATED_H2_PREFIX));
    if (existing) {
      // 抽取 H2 到下一 H2 之间的文本
      const lines = s.body.split('\n');
      const blockText = lines.slice(existing.start, existing.end).join('\n');
      const { newBlock, duplicates } = appendRelatedEntries(blockText, entities, concepts);
      newBody = replaceH2Block(s.body, existing.start, existing.end, newBlock);
      for (const d of duplicates) {
        pushWarning(s.relPath, `duplicate wikilink [[${d}]] 已在人工条目中存在,保留人工条目`);
        console.error(`WARN: ${s.relPath}: duplicate wikilink [[${d}]] 已在人工条目中存在,保留人工条目`);
      }
      action = 'related-appended';
    } else if (entities.length || concepts.length) {
      const block = renderRelatedBlock(entities, concepts);
      newBody = insertBeforeMaintain(s.body, block);
      action = 'related-created';
    } else {
      // 全部空,无区块也无新增 → 不动
      action = 'related-unchanged';
    }
    const newContent = renderFrontmatterBlock(s.fm, s.fmRaw) + '\n' + newBody;
    writes.push({ file: s.file, content: newContent, action });
  }

  // 7. 追加 + 保留:entity/concept 页 ## 来源资料 区块
  for (const ec of ecPages) {
    if (ec.invalid) continue;  // ajv 校验失败 → 跳过反链写(批次 3 P2-1:但仍进 warnings_by_file)
    if (ec.srcTypeErrs && ec.srcTypeErrs.length) continue;  // v0.6.5: sources 类型不符 → 跳过写盘(ERROR 已记,修复后重跑)
    const refs = ecToSources.get(ec.relPath) || [];
    let newBody = ec.body;
    let action;
    const existing = findH2Block(ec.body, (l) => l === SOURCES_H2 || l.startsWith(SOURCES_H2_PREFIX));
    if (existing) {
      const lines = ec.body.split('\n');
      const blockText = lines.slice(existing.start, existing.end).join('\n');
      const { newBlock, duplicates } = appendSourcesEntries(blockText, refs);
      newBody = replaceH2Block(ec.body, existing.start, existing.end, newBlock);
      for (const d of duplicates) {
        pushWarning(ec.relPath, `duplicate wikilink [[${d}]] 已在人工条目中存在,保留人工条目`);
        console.error(`WARN: ${ec.relPath}: duplicate wikilink [[${d}]] 已在人工条目中存在,保留人工条目`);
      }
      action = 'sources-appended';
    } else if (refs.length) {
      const block = renderSourcesBlock(refs);
      newBody = insertBeforeMaintain(ec.body, block);
      action = 'sources-created';
    } else {
      action = 'sources-unchanged';
    }
    const newContent = renderFrontmatterBlock(ec.fm, ec.fmRaw) + '\n' + newBody;
    writes.push({ file: ec.file, content: newContent, action });
  }

  // 8. 写盘(或 dry-run)
  // v0.6.5: result 新增 fail / errors_by_file(sources 类型不符 ERROR,与 lint-stub 输出字段对齐);
  //         errors 字段保持 v0.6.4 契约(写盘失败对象 {file, error})
  const result = {
    dry_run: dryRun,
    writes: [],
    errors: [],
    fail: flatErrors.length,
    errors_by_file: errorsByFile,
    warnings: flatWarnings,
    warnings_by_file: warningsByFile,
  };
  for (const w of writes) {
    result.writes.push({
      file: norm(w.file),
      action: w.action,
      bytes: Buffer.byteLength(w.content, 'utf8'),
    });
    if (!dryRun) {
      try {
        await fs.writeFile(w.file, w.content, 'utf8');
      } catch (e) {
        result.errors.push({ file: w.file, error: e.message });
      }
    }
  }

  console.log(JSON.stringify(result, null, 2));
  if (result.errors.length || result.fail > 0) process.exit(2);
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(2);
});
