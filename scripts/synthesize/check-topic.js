#!/usr/bin/env node
/**
 * check-topic.js — synthesize 步骤 0:topic 机械候选扫描 + syntheses/ 既有页清点
 * (实现权威:doc/design/implement-synthesize.md v0.1.0 冻结 §1.1;上游 PRD v0.5.6 §4.5)
 *
 * Usage:
 *   node scripts/synthesize/check-topic.js --project <用户工程根> --topic "<topic>" [--json]
 *
 * 行为:
 *   - knowledge/ 不存在 → ERROR exit 1(先跑 /aeps-llm-wiki-init)
 *   - 机械匹配规则(ponytail:候选预过滤,语义判定归 LLM):
 *       index.md 条目行(能解析出 `[title](rel)` markdown 链接的行)文本包含
 *       完整 topic 串或任一空白切分 token(长度 ≥ 2,大小写不敏感)即命中;
 *       无链接行(H1/H2/注释/空行)不登记,避免 `## Syntheses` 等标题噪声。
 *       命中是否阻塞(match_count = 0 → 提示先 ingest)由 SKILL.md 步骤 0 判定,
 *       本脚本一律 exit 0。
 *   - 行解析:`[title](rel)` 取行内第一个链接;rel 剥前导 `./` 与 `knowledge/`
 *     (= 相对 knowledge/ 的路径,可直接喂 gen-page --sources);
 *     行内 `#tag` 全量抽取(含 aggregate-index 渲染的灰色 <span> 后缀,
 *     tag 仅取 # 后 token,index 渲染只保留末段如 #fusa)。
 *   - 同时清点 knowledge/syntheses/*.md frontmatter(title / sources_count / updated)
 *     → syntheses[](LLM 语义比对 topic 与既有页,决定新建 vs update 路径;
 *       syntheses/ 目录不存在视为空,非错误)
 *   - frontmatter 解析:js-yaml 已有则用(scripts 现有依赖);不可用降级内置
 *     `key: value` 简易解析(清点只需 3 个标量字段,不新增 npm 依赖)
 *
 * JSON stdout 契约(--json):
 *   { ok: true, topic, match_count, matched: [{ title, rel, tags[] }],
 *     syntheses: [{ file, title, sources_count, updated }] }
 *   诊断 / 进度到 stderr;非 --json 时 stdout 输出人读摘要
 *   exit:0 正常(含 match_count = 0)/ 1 用法或环境错误
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

// js-yaml 已有则用,无则不引(降级路径见 parseFrontmatterText)
let yaml = null;
try {
  const _yamlNs = await import('js-yaml');
  yaml = _yamlNs.default ?? _yamlNs; // js-yaml ESM 无 default 导出,取命名空间兜底(#46 同根因,#57)
} catch {
  /* 降级到内置简易解析 */
}

function parseArgs(argv) {
  const args = { project: null, topic: null, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--topic') args.topic = argv[++i];
    else if (a === '--json') args.json = true;
  }
  return args;
}

// index 条目行形如 `- [title](./rel) —— description`(aggregate-index 渲染口径)
const MD_LINK_RE = /\[([^\]]+)\]\(([^)]+)\)/;
// 行内 #tag:# 前必须是行首 / 空白 / `>`(span 收尾),避免误吃 `####` 这类 H 标记
const TAG_RE = /(?:^|[\s>])#([A-Za-z0-9][A-Za-z0-9_/-]*)/g;

function extractTags(line) {
  return [...line.matchAll(TAG_RE)].map((m) => m[1]);
}

/** 剥 rel 前导 ./ 与 knowledge/,反斜杠归一正斜杠 → 相对 knowledge/ 的路径 */
function normalizeRel(raw) {
  let s = String(raw).trim().replace(/\\/g, '/');
  while (s.startsWith('./')) s = s.slice(2);
  if (s.startsWith('knowledge/')) s = s.slice('knowledge/'.length);
  return s;
}

/** 解析 index 条目行 → { title, rel } | null(无 markdown 链接的行不登记) */
function parseIndexLine(line) {
  const m = line.match(MD_LINK_RE);
  if (!m) return null;
  return { title: m[1].trim(), rel: normalizeRel(m[2]) };
}

/** 机械命中判定:行文本含完整 topic 串或任一空白切分 token(长度 ≥ 2),大小写不敏感 */
function lineHitsTopic(line, topicLower, tokensLower) {
  const lower = line.toLowerCase();
  if (topicLower && lower.includes(topicLower)) return true;
  return tokensLower.some((t) => lower.includes(t));
}

/**
 * 解析 frontmatter 文本 → 字典 | null。
 * js-yaml 优先;不可用 / 解析失败降级为 `key: value` 标量行解析
 * (syntheses 清点只需 title / sources_count / updated 三个标量,列表项不深挖)
 */
function parseFrontmatterText(text) {
  const m = text.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)/);
  if (!m) return null;
  if (yaml) {
    try {
      return yaml.load(m[1]) || {};
    } catch {
      /* 落到简易解析 */
    }
  }
  const fm = {};
  for (const line of m[1].split(/\r?\n/)) {
    const km = line.match(/^([\w-]+):\s*(.*)$/);
    if (!km) continue;
    let v = km[2].trim();
    if (v.length >= 2 && ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'")))) {
      v = v.slice(1, -1);
    }
    fm[km[1]] = v;
  }
  return fm;
}

/** 清点 knowledge/syntheses/*.md → [{ file, title, sources_count, updated }],按 file 字典序 */
async function collectSyntheses(synDir) {
  let entries;
  try {
    entries = await fs.readdir(synDir, { withFileTypes: true });
  } catch {
    return []; // syntheses/ 不存在 = 还没有任何综合页,非错误
  }
  const out = [];
  for (const ent of entries) {
    if (!ent.isFile() || !ent.name.toLowerCase().endsWith('.md')) continue;
    let fm = null;
    try {
      fm = parseFrontmatterText(await fs.readFile(path.join(synDir, ent.name), 'utf8'));
    } catch {
      fm = null; // 读失败按无 frontmatter 处理,不中断清点
    }
    const fallbackTitle = ent.name.replace(/\.md$/i, '');
    const count = fm ? Number(fm.sources_count) : NaN;
    out.push({
      file: `syntheses/${ent.name}`,
      title: fm && typeof fm.title === 'string' && fm.title.trim() ? fm.title.trim() : fallbackTitle,
      sources_count: Number.isFinite(count) ? count : null,
      updated: fm && typeof fm.updated === 'string' ? fm.updated : null,
    });
  }
  out.sort((a, b) => (a.file < b.file ? -1 : a.file > b.file ? 1 : 0));
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.project) {
    console.error('ERROR: --project <用户工程根> 必填');
    process.exit(1);
  }
  if (!args.topic || !String(args.topic).trim()) {
    console.error('ERROR: --topic "<topic>" 必填(不能为空白)');
    process.exit(1);
  }

  const project = path.resolve(args.project);
  const knowledgeDir = path.join(project, 'knowledge');
  const knowledgeExists = await fs.access(knowledgeDir).then(() => true).catch(() => false);
  if (!knowledgeExists) {
    console.error(`ERROR: knowledge/ 目录不存在: ${knowledgeDir}(先跑 /aeps-llm-wiki-init)`);
    process.exit(1);
  }

  const topic = String(args.topic).trim();
  const topicLower = topic.toLowerCase();
  const tokensLower = topic
    .split(/\s+/)
    .filter((t) => t.length >= 2)
    .map((t) => t.toLowerCase());

  // index.md 缺失按空内容处理:命中 0 条走 SKILL.md 的"先 ingest 再 synthesize"提示路径
  const indexPath = path.join(knowledgeDir, 'index.md');
  const indexExists = await fs.access(indexPath).then(() => true).catch(() => false);
  if (!indexExists) {
    console.error('WARN: knowledge/index.md 不存在(先跑 aggregate-index 或 ingest);按空 index 处理');
  }
  const indexText = indexExists ? await fs.readFile(indexPath, 'utf8') : '';

  const matched = [];
  for (const line of indexText.split(/\r?\n/)) {
    const entry = parseIndexLine(line);
    if (!entry) continue; // 无链接行(H1/H2/注释)不登记
    if (!lineHitsTopic(line, topicLower, tokensLower)) continue;
    matched.push({ ...entry, tags: extractTags(line) });
  }

  const syntheses = await collectSyntheses(path.join(knowledgeDir, 'syntheses'));

  console.error(
    `[check-topic] topic="${topic}" 候选命中 ${matched.length} 条;既有 synthesis 页 ${syntheses.length} 篇`
  );
  if (args.json) {
    console.log(JSON.stringify(
      { ok: true, topic, match_count: matched.length, matched, syntheses },
      null,
      2,
    ));
  } else {
    const lines = [`topic: ${topic}`];
    lines.push(`候选命中 ${matched.length} 条(knowledge/index.md):`);
    for (const m of matched) {
      lines.push(`  - [${m.title}](${m.rel})${m.tags.length ? ' #' + m.tags.join(' #') : ''}`);
    }
    lines.push(`既有 synthesis 页 ${syntheses.length} 篇(knowledge/syntheses/):`);
    for (const s of syntheses) {
      lines.push(`  - ${s.file} — ${s.title}(sources_count=${s.sources_count}, updated=${s.updated ?? '-'})`);
    }
    console.log(lines.join('\n'));
  }
  process.exit(0);
}

main().catch((err) => {
  console.error(`ERROR: ${err.message}`);
  process.exit(1);
});
