#!/usr/bin/env node
/**
 * check-qmd.mjs — query skill 跑前探查脚本
 *
 * 单次运行即退,不开 daemon。
 *
 * 行为:
 *   1. 跑 `qmd --version` 探查 qmd 是否可用
 *   2. 数 <project>/knowledge/ 下的 md 页数 N
 *   3. 按阈值返回 SKILL.md 需要的探查结果(JSON 格式打印到 stdout)
 *
 * 输出(JSON):
 *   {
 *     "pageCount": <N>,
 *     "qmdAvailable": <bool>,
 *     "qmdVersion": "<version>" | null,
 *     "engine": "index" | "qmd" | "fail",
 *     "reason": "<降级或失败的提示文案>"
 *   }
 *
 * 决策表(与 design §4.3 / prd §4.3 一致):
 *   N < 500                    → engine=index, 不需要 qmd
 *   500 ≤ N < 1000 + qmd 在   → engine=qmd
 *   500 ≤ N < 1000 + qmd 不在 → engine=index(reason=提示用户装 qmd)
 *   N ≥ 1000 + qmd 在          → engine=qmd
 *   N ≥ 1000 + qmd 不在        → engine=fail(reason=必须装 qmd)
 *
 * 用法:
 *   node ./scripts/check-qmd.mjs --project-dir .
 */

import { execSync } from 'node:child_process';
import { globSync } from 'node:fs';
import { readdirSync, statSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';

const QUERY_INDEX_THRESHOLD = 500;
const QUERY_QMD_REQUIRED_THRESHOLD = 1000;

function parseArgs(argv) {
  const args = { projectDir: '.' };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === '--project-dir' && argv[i + 1]) {
      args.projectDir = argv[i + 1];
      i++;
    }
  }
  return args;
}

function countPages(projectDir) {
  // 数 knowledge/**/*.md 文件数(递归)
  const knowledgeDir = resolve(projectDir, 'knowledge');
  if (!existsSync(knowledgeDir)) return 0;

  let count = 0;
  function walk(dir) {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const stat = statSync(full);
      if (stat.isDirectory()) walk(full);
      else if (entry.endsWith('.md')) count++;
    }
  }
  walk(knowledgeDir);
  return count;
}

function probeQmd() {
  try {
    const version = execSync('qmd --version', { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    return { available: true, version };
  } catch {
    return { available: false, version: null };
  }
}

function decideEngine(pageCount, qmdAvailable) {
  if (pageCount < QUERY_INDEX_THRESHOLD) {
    return { engine: 'index', reason: null };
  }
  if (pageCount >= QUERY_QMD_REQUIRED_THRESHOLD) {
    if (qmdAvailable) return { engine: 'qmd', reason: null };
    return {
      engine: 'fail',
      reason: `wiki 已 ${pageCount} 页(阈值 ${QUERY_QMD_REQUIRED_THRESHOLD}),必须装 qmd 才能 query。请 npm install -g @tobilu/qmd`,
    };
  }
  // 500 <= N < 1000
  if (qmdAvailable) return { engine: 'qmd', reason: null };
  return {
    engine: 'index',
    reason: `wiki 已 ${pageCount} 页,推荐装 qmd 提升命中率。请 npm install -g @tobilu/qmd(未装不影响运行,降级走 index.md)`,
  };
}

function main() {
  const args = parseArgs(process.argv);
  const pageCount = countPages(args.projectDir);
  const qmd = probeQmd();
  const decision = decideEngine(pageCount, qmd.available);

  const result = {
    pageCount,
    qmdAvailable: qmd.available,
    qmdVersion: qmd.version,
    engine: decision.engine,
    reason: decision.reason,
  };
  console.log(JSON.stringify(result, null, 2));

  // fail 模式退出码非零,让 SKILL.md 早退
  process.exit(decision.engine === 'fail' ? 2 : 0);
}

main();