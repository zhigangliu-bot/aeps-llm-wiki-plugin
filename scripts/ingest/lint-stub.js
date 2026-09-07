#!/usr/bin/env node
/**
 * lint-stub.js — M2.4 lint skill 预留 stub
 *
 * 本脚本是 lint skill (M2.4 任务) 的接口占位。当前实现只输出固定 JSON,不真做校验。
 * SKILL.md 步骤 19 调 `node scripts/ingest/lint-stub.js --project <dir>` 解析输出。
 *
 * 接口契约(锁定):
 *   - 输入:--project <dir>  (必填)
 *   - 输出(stdout): JSON 形如:
 *       {
 *         "project": "<dir>",
 *         "linted":  <number>,   // 扫到的 knowledge/ 页数
 *         "fail":    <number>,   // lint C17/C18/C19 失败数(目前永远 0)
 *         "warn":    <number>,   // lint WARN 数(目前永远 0)
 *         "stub":    true,
 *         "lint_version": "M2.4-stub",
 *         "scanned_at": "<ISO 8601>"
 *       }
 *   - Exit code:
 *       0 - 成功(总是;真实 lint 失败 FAIL 时会改非零)
 *       1 - 参数错
 *
 * 设计原则:
 *   - **不动 lint 真实实现**:M2.4 任务会替换本 stub 内容,但接口契约(stdin/stdout/exit)不变。
 *   - **不破坏 SKILL.md 步骤 19 编排**:本 stub 输出 JSON 含 `linted` / `fail` / `warn` 字段,SKILL.md
 *     可正常解析;后续 M2.4 实现只需保证字段含义一致。
 *   - **不引入新依赖**:仅用 node:fs / node:path / node:process,无 npm 包。
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const STUB_VERSION = 'M2.4-stub';

/**
 * 扫 <project>/knowledge/ 下所有 .md 页数(排除 .gitkeep / 隐藏文件)。
 * 与 lint 真实实现扫的范围对齐。
 */
async function countKnowledgePages(project) {
  const knowledgeDir = path.join(project, 'knowledge');
  let count = 0;
  async function walk(dir) {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return; // knowledge/ 不存在 → 0
    }
    for (const e of entries) {
      if (e.name.startsWith('.')) continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        await walk(full);
      } else if (e.isFile() && e.name.endsWith('.md')) {
        count++;
      }
    }
  }
  await walk(knowledgeDir);
  return count;
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
  const linted = await countKnowledgePages(project);

  // 当前 stub:fail=0, warn=0;M2.4 真实 lint 会跑 C17/C18/C19 填这两个字段
  const out = {
    project: project.replace(/\\/g, '/'),
    linted,
    fail: 0,
    warn: 0,
    stub: true,
    lint_version: STUB_VERSION,
    scanned_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
  };
  console.log(JSON.stringify(out, null, 2));
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(2);
});