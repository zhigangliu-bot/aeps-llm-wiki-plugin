#!/usr/bin/env node
/**
 * comparison-counter.js — 路径 B 计数器持久化(query 步骤 8 / 11.5,design §7.5)
 *
 * Usage:
 *   node scripts/query/comparison-counter.js read      --project <用户工程根> --json
 *   node scripts/query/comparison-counter.js increment --project <用户工程根> --theme "<主题短语>" --json
 *   node scripts/query/comparison-counter.js reset     --project <用户工程根> --json
 *
 * 持久化:<project>/knowledge/.aeps-state/comparison-counter.json
 *   结构:{ "count": 0, "themes": [], "updated": "<ISO 8601>" }
 *
 * 语义(implement-query.md v0.1.0 冻结读法 A):
 *   - increment:**仅在 intent=comparison 且用户拍板落档 analysis 后**由 SKILL.md 调用
 *     (非 comparison 落档不动计数;避免噪声查询污染计数)
 *   - reset:仅用户拍板建常驻 comparison 页后归零(SKILL.md 编排,脚本不自动触发)
 *   - read → { count, should_propose, themes, updated },should_propose = count >= 3
 *   - .aeps-state/ 目录不存在 → 写入时自动创建;read 对缺失文件幂等返回零值(无副作用)
 *
 * JSON stdout 契约:结构化 JSON 到 stdout,诊断到 stderr;
 * exit 0 成功 / 1 用法或环境错误(缺 --project / 缺 --theme / 非法子命令 /
 * increment / reset 时 knowledge/ 目录不存在;read 只读零值不校验)
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

// 路径 B 触发阈值:累计 ≥ 3 次"X vs Y" → 下次落档询问时提议常驻 comparison 页(PRD §4.6)
const PROPOSE_THRESHOLD = 3;

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function usageError(msg) {
  console.error(`ERROR: ${msg}`);
  console.error('Usage: node comparison-counter.js <read|increment|reset> --project <dir> [--theme "<主题>"] --json');
  process.exit(1);
}

function parseArgs(argv) {
  const args = { subcommand: argv[0], project: null, theme: null, json: false };
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--theme') args.theme = argv[++i];
    else if (a === '--json') args.json = true;
  }
  return args;
}

/** 读状态文件;不存在 → 零值;损坏 → WARN + 零值(回滚点:删文件后 increment 自动重建) */
async function readState(stateFile) {
  try {
    const txt = await fs.readFile(stateFile, 'utf8');
    const st = JSON.parse(txt);
    return {
      count: Number.isFinite(st.count) ? st.count : 0,
      themes: Array.isArray(st.themes) ? st.themes : [],
      updated: typeof st.updated === 'string' ? st.updated : null,
    };
  } catch (e) {
    if (e.code === 'ENOENT') return { count: 0, themes: [], updated: null };
    console.error(`WARN: 状态文件损坏,按零值重建(${e.message})`);
    return { count: 0, themes: [], updated: null };
  }
}

async function writeState(stateFile, state) {
  // .aeps-state/ 目录不存在 → 自动创建(契约 §1.1)
  await fs.mkdir(path.dirname(stateFile), { recursive: true });
  await fs.writeFile(stateFile, JSON.stringify(state, null, 2) + '\n', 'utf8');
}

function emit(args, extra) {
  const payload = { ...extra };
  payload.should_propose = payload.count >= PROPOSE_THRESHOLD;
  console.error(`[comparison-counter] count=${payload.count} should_propose=${payload.should_propose}`);
  console.log(JSON.stringify(payload, null, 2));
  process.exit(0);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!['read', 'increment', 'reset'].includes(args.subcommand)) {
    usageError(`非法子命令: ${args.subcommand}(合法值: read | increment | reset)`);
  }
  if (!args.project) usageError('--project <用户工程根> 必填');

  const project = path.resolve(args.project);
  const knowledgeDir = path.join(project, 'knowledge');
  const stateFile = path.join(knowledgeDir, '.aeps-state', 'comparison-counter.json');

  // 写分支(increment / reset)先验证 knowledge/ 存在:防止 --project 笔误在错误位置
  // 静默创建 knowledge/.aeps-state/(对齐 count-pages / append-log 环境错误约定 exit 1);
  // read 只读零值、无写副作用,不校验(缺失文件幂等,见 readState)
  if (args.subcommand !== 'read') {
    const knowledgeExists = await fs.access(knowledgeDir).then(() => true).catch(() => false);
    if (!knowledgeExists) {
      console.error(`ERROR: knowledge/ 目录不存在: ${knowledgeDir}(先跑 /aeps-llm-wiki-init)`);
      process.exit(1);
    }
  }

  if (args.subcommand === 'read') {
    const st = await readState(stateFile);
    emit(args, { action: 'read', count: st.count, themes: st.themes, updated: st.updated });
  } else if (args.subcommand === 'increment') {
    if (!args.theme || !String(args.theme).trim()) usageError('increment 必须传 --theme "<主题短语>"');
    const st = await readState(stateFile);
    const next = {
      count: st.count + 1,
      themes: [...st.themes, String(args.theme).trim()],
      updated: nowIso(),
    };
    await writeState(stateFile, next);
    emit(args, { action: 'increment', count: next.count, themes: next.themes, updated: next.updated });
  } else {
    // reset:用户拍板建常驻 comparison 页后归零(SKILL.md 编排触发,脚本不自动调)
    const now = nowIso();
    await writeState(stateFile, { count: 0, themes: [], updated: now });
    emit(args, { action: 'reset', count: 0, themes: [], updated: now });
  }
}

main().catch((err) => {
  console.error(`ERROR: ${err.message}`);
  process.exit(2);
});
