#!/usr/bin/env node
/**
 * append-log.js — query 步骤 11:向 knowledge/log.md 追加 **Creation** 行
 *
 * Usage:
 *   node scripts/query/append-log.js --project <用户工程根> \
 *     --question "<原问句>" --analysis-path "analyses/<file>.md" [--skip-analysis] --json
 *
 * 行为(implement-query.md §1.1,对齐 doc/template/page-log.md + schema.md §4 示例):
 *   - 写入行:
 *       **Creation**: query "<question>" → analyses/<file>.md
 *     --skip-analysis 时(gating 判定不落档 / 用户拒绝,SKILL.md 显式选择留痕):
 *       **Creation**: query "<question>" → (未落档)
 *     默认不传不写(log 只记落档,拒绝不进 log,避免噪声)。
 *   - 已有当天 `## [YYYY-MM-DD]` H2 → 行追加到该 H2 下**末尾**(注意与 ingest
 *     append-log 的"顶部追加"不同,本脚本是 query 独立实现,不复用 ingest 契约)
 *   - 无当天 H2 → 新 H2 插到最新在前位置(第一个更旧日期 H2 之前;
 *     无更旧 → `## 维护` 节之前;无 → 文件末尾)
 *   - 已有 frontmatter / 旧日期节 / `## 维护` 节原样保留(round-trip 安全)
 *
 * 边界:
 *   - knowledge/ 目录不存在 → ERROR exit 1(先跑 init)
 *   - log.md 不存在 → 创建(仅当天 H2 + 行,不代写 init 骨架)
 *   - --analysis-path 归一:剥前导 knowledge/ 与 ./,反斜杠归一正斜杠
 *
 * JSON stdout 契约:
 *   { "written": true, "date": "YYYY-MM-DD", "action": "appended|new-section|created",
 *     "log_path": "...", "line": "..." }
 *   exit 0 成功 / 1 用法或环境错误 / 2 写盘失败
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function parseArgs(argv) {
  const args = { project: null, question: null, analysisPath: null, skipAnalysis: false, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--question') args.question = argv[++i];
    else if (a === '--analysis-path') args.analysisPath = argv[++i];
    else if (a === '--skip-analysis') args.skipAnalysis = true;
    else if (a === '--json') args.json = true;
  }
  return args;
}

const DATE_H2_RE = /^##\s+\[(\d{4}-\d{2}-\d{2})\]\s*$/;

/** 归一 --analysis-path:剥前导 knowledge/ 与 ./;反斜杠 → 正斜杠 */
function normalizeAnalysisPath(p) {
  let s = String(p).trim().replace(/\\/g, '/');
  while (s.startsWith('./')) s = s.slice(2);
  if (s.startsWith('knowledge/')) s = s.slice('knowledge/'.length);
  return s;
}

/**
 * 在 lines 中定位当天节:
 *   返回 { h2Idx, endIdx } — endIdx 为节内容区exclusive上界
 *   (下一个日期 H2 行 / `## 维护` 行 / lines.length 三者取最小且 > h2Idx)
 */
function findSection(lines, today) {
  let h2Idx = -1;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(DATE_H2_RE);
    if (m && m[1] === today) { h2Idx = i; break; }
  }
  if (h2Idx === -1) return null;
  let endIdx = lines.length;
  for (let i = h2Idx + 1; i < lines.length; i++) {
    if (DATE_H2_RE.test(lines[i]) || lines[i].trim() === '## 维护') { endIdx = i; break; }
  }
  return { h2Idx, endIdx };
}

/** 把行追加到当天节末尾(`---` 水平线之前,保持节尾水平线语义) */
function appendIntoSection(lines, section, line) {
  const { h2Idx, endIdx } = section;
  // 从节尾向上找最后一个非空行 p(h2Idx < p < endIdx)
  let p = endIdx - 1;
  while (p > h2Idx && lines[p].trim() === '') p--;
  if (p === h2Idx) {
    // 空节:H2 后直接放行
    lines.splice(h2Idx + 1, 0, '', line);
    return;
  }
  if (lines[p].trim() === '---') {
    // 有水平线:插到 `---` 之前,且 line 与 `---` 之间留空行
    //(`---` 紧跟文本行会被 markdown 解析成 setext H2,必须隔开)
    const prevBlank = p - 1 > h2Idx && lines[p - 1].trim() === '';
    lines.splice(p, 0, ...(prevBlank ? [line, ''] : ['', line, '']));
    return;
  }
  // 普通内容节尾:空行 + line
  lines.splice(p + 1, 0, '', line);
}

/** 新日期节插入:最新在前(第一个更旧日期 H2 之前;fallback `## 维护` / EOF) */
function insertNewSection(lines, today, line) {
  let insertAt = -1;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(DATE_H2_RE);
    if (m && m[1] < today) { insertAt = i; break; }
  }
  if (insertAt === -1) {
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim() === '## 维护') { insertAt = i; break; }
    }
  }
  const block = [`## [${today}]`, '', line, ''];
  if (insertAt === -1 || insertAt >= lines.length) {
    // EOF:剥掉 split 产生的尾部空串,补规范结尾
    while (lines.length && lines[lines.length - 1].trim() === '') lines.pop();
    lines.push(...block);
    return;
  }
  // 中间插入:与上文留空行分隔
  if (insertAt > 0 && lines[insertAt - 1].trim() !== '' && lines[insertAt - 1].trim() !== '---') {
    block.unshift('');
  }
  lines.splice(insertAt, 0, ...block);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.project) { console.error('ERROR: --project <用户工程根> 必填'); process.exit(1); }
  if (!args.question || !String(args.question).trim()) {
    console.error('ERROR: --question "<原问句>" 必填');
    process.exit(1);
  }
  if (!args.skipAnalysis && !args.analysisPath) {
    console.error('ERROR: --analysis-path 必填(除非显式传 --skip-analysis 记 "(未落档)" 留痕行)');
    process.exit(1);
  }

  const project = path.resolve(args.project);
  const knowledgeDir = path.join(project, 'knowledge');
  const logPath = path.join(knowledgeDir, 'log.md');

  const knowledgeExists = await fs.access(knowledgeDir).then(() => true).catch(() => false);
  if (!knowledgeExists) {
    console.error(`ERROR: knowledge/ 目录不存在: ${knowledgeDir}(先跑 /aeps-llm-wiki-init)`);
    process.exit(1);
  }

  const today = nowIso().slice(0, 10); // UTC 日期,对齐 ingest append-log 口径
  const line = args.skipAnalysis
    ? `**Creation**: query "${args.question}" → (未落档)`
    : `**Creation**: query "${args.question}" → ${normalizeAnalysisPath(args.analysisPath)}`;

  const logExists = await fs.access(logPath).then(() => true).catch(() => false);
  const existedBefore = logExists;
  const content = logExists ? await fs.readFile(logPath, 'utf8') : '';
  const lines = content.split('\n');

  let action;
  const section = findSection(lines, today);
  if (section) {
    appendIntoSection(lines, section, line);
    action = 'appended';
  } else {
    insertNewSection(lines, today, line);
    action = existedBefore ? 'new-section' : 'created';
  }

  try {
    await fs.writeFile(logPath, lines.join('\n'), 'utf8');
  } catch (e) {
    console.error(`ERROR: 写 log.md 失败: ${e.message}`);
    process.exit(2);
  }

  console.error(`[append-log] ${action} @ ${today}: ${line}`);
  console.log(JSON.stringify({
    written: true,
    date: today,
    action,
    log_path: logPath.replace(/\\/g, '/'),
    line,
  }, null, 2));
  process.exit(0);
}

main().catch((err) => {
  console.error(`ERROR: ${err.message}`);
  process.exit(2);
});
