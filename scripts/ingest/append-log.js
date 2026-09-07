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
 * Exit codes:
 *   0 - 成功
 *   1 - 参数错
 *   2 - 写盘失败
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import yaml from 'js-yaml';

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
 * 每个 H2 ## YYYY-MM-DD 占一段
 */
function parseLogSections(body) {
  const lines = body.split('\n');
  const sections = [];
  let cur = null;
  for (const line of lines) {
    const m = line.match(/^##\s+(\d{4}-\d{2}-\d{2})\s*$/);
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
  return sections;
}

/**
 * 把 sections 拼回 body
 */
function renderLogSections(sections) {
  if (!sections.length) return '';
  const out = [];
  for (const s of sections) {
    out.push(`## ${s.date}`);
    out.push('');
    out.push(...s.content);
  }
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd() + '\n';
}

/**
 * 构造本次 ingest 的日志条目
 * 形如:
 *   **Ingest**: inbox/foo.pdf → raw/06_功能安全/foo.pdf (+ .converted.md);新建 [[foo]] [[bar]]
 */
function buildEntries(files) {
  const lines = [];
  for (const f of files) {
    const fileName = path.basename(f.path);
    const sub = f.target_subdir || '?';
    const target = `raw/${sub}/${fileName}`;
    let entry = `**Ingest**: inbox/${fileName} → ${target}`;
    if (f.converted_path) entry += ` (+ .converted.md)`;
    entry += ';新建 ';
    entry += `[[${path.basename(fileName, path.extname(fileName))}]]`;
    lines.push(entry);
  }
  return lines;
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

  const result = { dry_run: dryRun, date: today, entries_added: entries.length, log_path: logPath.replace(/\\/g, '/') };
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
