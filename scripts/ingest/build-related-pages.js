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
 * 每次 ingest 完全重建,不保留人工条目
 *
 * Exit codes:
 *   0 - 成功
 *   1 - 参数错
 *   2 - 写盘失败
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import yaml from 'js-yaml';
import Ajv from 'ajv';

// ---- ajv 校验 (对齐 frontmatter.schema.json) ----
// 失败语义(对齐 SKILL.md §失败语义):
//   - ajv 加载 schema 失败 → process.exit(2)
//   - ajv 校验 entity/concept frontmatter 失败 → stderr WARN + 跳过该页(反链不写)
const SCHEMA_PATH = path.resolve(import.meta.dirname, '..', '..', 'doc', 'schema', 'frontmatter.schema.json');
let ajvValidate = null;

async function loadValidator() {
  if (ajvValidate) return ajvValidate;
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

// 实体 / 概念子目录列表(对齐 doc/schema/schema.md §1.1: 18 叶子 1:1 绑死)
// entity.concept. 子目录 7 个;concept.* 子目录 7 个
const ENTITY_DIRS = ['person', 'organization', 'project', 'product', 'event', 'place', 'other'];
const CONCEPT_DIRS = ['theory', 'method', 'field', 'phenomenon', 'standard', 'term', 'other'];

const RELATED_H2 = '## 相关页面(Related Pages,由 ingest 自动生成)';
const RELATED_ENTITIES_H3 = '### Entities';
const RELATED_CONCEPTS_H3 = '### Concepts';
const SOURCES_H2 = '## 来源资料(由 ingest 自动生成)';

// 反链区块说明文字(对齐 page-source.md L111 / page-entity-*.md L55):
// 本节由 /aeps-llm-wiki-ingest 双向反链生成,每次 ingest 完全重建,不保留人工添加的条目。
const RELATED_DESC = '本节由 `/aeps-llm-wiki-ingest` 根据本源页抽取并创建的实体页、概念页生成,每次 ingest **完全重建**,不保留人工添加的条目;没有任何相关页面时省略本节。';
const SOURCES_DESC = '本节由 `/aeps-llm-wiki-ingest` 根据抽取本页的 `type: source` 源页列表生成,作为 source 页 `## 相关页面(Related Pages)` 的反向链接(双向反链)。每次 ingest **完全重建**,不保留人工添加的条目;没有任何 source 页引用本页时省略本节。';

// ---- frontmatter 解析 ----
function parseFrontmatter(mdText) {
  const m = mdText.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  if (!m) return { fm: {}, body: mdText };
  let fm = {};
  try { fm = yaml.load(m[1]) || {}; } catch { fm = {}; }
  return { fm, body: m[2] };
}

// 渲染 frontmatter block (保留原样)
function renderFrontmatterBlock(fm) {
  return '---\n' + yaml.dump(fm, { lineWidth: -1, quotingType: '"', forceQuotes: false }) + '---\n';
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
    const { fm, body } = parseFrontmatter(txt);
    if (fm.type !== 'source') continue;
    out.push({
      file: f,
      relPath: norm(path.relative(knowledgeDir, f)),
      slug: path.basename(f, '.md'),
      title: fm.title || path.basename(f, '.md'),
      resource: norm(fm.resource || ''),
      fm,
      body,
    });
  }
  return out;
}

// 扫 entity/concept 页
// 失败语义(对齐 SKILL.md §失败语义):
//   - ajv 校验失败 → stderr WARN + 跳过该页(反链不写)
async function scanEntityConcept(knowledgeDir) {
  const validate = await loadValidator();
  const out = [];
  // entities/*/*
  for (const sub of ENTITY_DIRS) {
    const dir = path.join(knowledgeDir, 'entities', sub);
    for (const f of await listMarkdown(dir)) {
      const txt = await fs.readFile(f, 'utf8');
      const { fm, body } = parseFrontmatter(txt);
      if (!fm.type || !fm.type.startsWith('entity.')) continue;
      if (!validate(fm)) {
        const errs = (validate.errors || []).map(e => `${e.instancePath || '/'} ${e.message}`).join('; ');
        console.error(`WARN: ${f}: ${errs}`);
        continue;
      }
      out.push({
        file: f,
        relPath: norm(path.relative(knowledgeDir, f)),
        slug: path.basename(f, '.md'),
        title: fm.title || path.basename(f, '.md'),
        type: fm.type,
        sources: Array.isArray(fm.sources) ? fm.sources : [],
        fm,
        body,
      });
    }
  }
  for (const sub of CONCEPT_DIRS) {
    const dir = path.join(knowledgeDir, 'concepts', sub);
    for (const f of await listMarkdown(dir)) {
      const txt = await fs.readFile(f, 'utf8');
      const { fm, body } = parseFrontmatter(txt);
      if (!fm.type || !fm.type.startsWith('concept.')) continue;
      if (!validate(fm)) {
        const errs = (validate.errors || []).map(e => `${e.instancePath || '/'} ${e.message}`).join('; ');
        console.error(`WARN: ${f}: ${errs}`);
        continue;
      }
      out.push({
        file: f,
        relPath: norm(path.relative(knowledgeDir, f)),
        slug: path.basename(f, '.md'),
        title: fm.title || path.basename(f, '.md'),
        type: fm.type,
        sources: Array.isArray(fm.sources) ? fm.sources : [],
        fm,
        body,
      });
    }
  }
  return out;
}

// ---- 区块渲染 ----
function renderRelatedBlock(entities, concepts) {
  if (!entities.length && !concepts.length) return null;
  const lines = [RELATED_H2, '', RELATED_DESC, ''];
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
  const lines = [SOURCES_H2, '', SOURCES_DESC, ''];
  for (const s of sourceRefs.sort((a, b) => a.title.localeCompare(b.title))) {
    lines.push(`- [[${s.slug}]]`);
  }
  lines.push('');
  return lines.join('\n');
}

// ---- body 区块替换 ----
/**
 * 删除 body 中已有的 RELATED_H2 / SOURCES_H2 区块(到下一个 H2 或文末)
 * 同步吃掉紧随其后的 `---` 水平线(避免 rebuild 时累积多个)
 * 保留 ## 维护说明 等其他 H2
 */
function stripExistingBlock(body, h2Name) {
  // 匹配以 h2Name 开头的 H2,直到下一个 ## (任意 H2) 或文末
  const lines = body.split('\n');
  const out = [];
  let inBlock = false;
  let afterBlockEaten = false;  // 是否刚退出 block(用于吃 --- 水平线)
  for (const line of lines) {
    if (!inBlock && line.trim() === h2Name) {
      inBlock = true;
      afterBlockEaten = false;
      continue;
    }
    if (inBlock) {
      if (/^##\s/.test(line.trim())) {
        inBlock = false;
        // 退出 block 后,看下一行是不是 ---
        afterBlockEaten = true;
        out.push(line);
        continue;
      }
      // skip until next H2
      continue;
    }
    if (afterBlockEaten && line.trim() === '---') {
      // 吃掉本行 `---`(残留的旧水平线);但只吃一次
      afterBlockEaten = false;
      continue;
    }
    afterBlockEaten = false;
    out.push(line);
  }
  // 去掉末尾多余空行
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd();
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
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
  const ecToSources = new Map(); // ec.relPath → [{ slug, title }]
  for (const ec of ecPages) {
    const refs = [];
    for (const src of ec.sources) {
      if (!src.resource) continue;
      const r = norm(src.resource);
      let matched = sourceByResource.get(r);
      if (!matched) {
        // 尝试 ./knowledge/sources/{slug}.md
        const m2 = r.match(/knowledge\/sources\/([^/]+)\.md$/);
        if (m2) matched = sourceBySlug.get(m2[1]);
      }
      if (matched) {
        refs.push({ slug: matched.slug, title: matched.title });
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
      if (!src.resource) continue;
      const r = norm(src.resource);
      let matched = sourceByResource.get(r);
      if (!matched) {
        const m2 = r.match(/knowledge\/sources\/([^/]+)\.md$/);
        if (m2) matched = sourceBySlug.get(m2[1]);
      }
      if (!matched) continue;
      const bucket = sourceToEc.get(matched.slug);
      if (!bucket) continue;
      if (ec.type.startsWith('entity.')) bucket.entities.push({ slug: ec.slug, title: ec.title });
      else if (ec.type.startsWith('concept.')) bucket.concepts.push({ slug: ec.slug, title: ec.title });
    }
  }

  const writes = [];

  // 6. 重写所有 source 页(完全重建 ## 相关页面 区块)
  for (const s of sources) {
    // 仅重建本 batch 涉及的 source 页(性能 + 减少误改)
    // 但为了"每次完全重建",扫到的所有 source 都重建
    // 实现策略:对 sources 全量重建
    const { entities, concepts } = sourceToEc.get(s.slug) || { entities: [], concepts: [] };
    const block = renderRelatedBlock(entities, concepts);

    // 重写 body
    let newBody = stripExistingBlock(s.body, RELATED_H2);
    if (block) {
      newBody = insertBeforeMaintain(newBody, block);
    } else {
      // 全部空 → 省整节(已通过 stripExistingBlock 删掉)
      newBody = newBody.trimEnd() + '\n';
    }
    const newContent = renderFrontmatterBlock(s.fm) + '\n' + newBody;
    writes.push({ file: s.file, content: newContent, action: block ? 'related-updated' : 'related-removed' });
  }

  // 7. 重写所有 entity/concept 页(完全重建 ## 来源资料 区块)
  for (const ec of ecPages) {
    const refs = ecToSources.get(ec.relPath) || [];
    const block = renderSourcesBlock(refs);

    let newBody = stripExistingBlock(ec.body, SOURCES_H2);
    if (block) {
      newBody = insertBeforeMaintain(newBody, block);
    } else {
      newBody = newBody.trimEnd() + '\n';
    }
    const newContent = renderFrontmatterBlock(ec.fm) + '\n' + newBody;
    writes.push({ file: ec.file, content: newContent, action: block ? 'sources-updated' : 'sources-removed' });
  }

  // 8. 写盘(或 dry-run)
  const result = { dry_run: dryRun, writes: [], errors: [] };
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
  if (result.errors.length) process.exit(2);
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(2);
});
