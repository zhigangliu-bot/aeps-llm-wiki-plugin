#!/usr/bin/env node
/**
 * preflight.js — ingest skill 启动前的依赖检查
 *
 * 用途:
 *   检测 scripts/node_modules/ 是否齐备;缺失 → 提示用户装,exit 2
 *   SKILL.md 步骤 0.5 在跑 scan-inbox.js 之前主动调用,避免首次 spawn 才暴露
 *   `Cannot find module 'js-yaml'` 类错误。
 *
 * 用法:
 *   node scripts/ingest/preflight.js [--scripts-dir <dir>] [--json]
 *
 * 参数:
 *   --scripts-dir    指向包含 package.json + node_modules 的目录
 *                    (默认 process.cwd() 或 PLUGIN_ROOT/scripts)
 *   --json           输出 JSON 到 stdout(默认 stdout 为 JSON)
 *
 * 退出码:
 *   0 - 依赖齐备
 *   1 - 参数错
 *   2 - 缺依赖(列出缺失项 + 提示 npm install)
 *
 * JSON stdout:
 *   ok=true   : { ok: true, scripts_dir: ..., modules_dir: ..., modules: [...], missing: [] }
 *   ok=false  : { ok: false, scripts_dir: ..., modules_dir: ..., missing: [...] }
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

// 必装依赖(对齐 scripts/package.json 的 dependencies)
const REQUIRED = ['js-yaml', 'ajv', '@firecrawl/anydoc'];

function parseArgs(argv) {
  const args = { scripts_dir: null, json: true };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--scripts-dir') args.scripts_dir = argv[++i];
    else if (a === '--json') args.json = true;
  }
  return args;
}

/**
 * 解析 scripts_dir 候选:
 *   1. --scripts-dir 显式传入
 *   2. process.env.PLUGIN_ROOT/scripts(plugin 仓 cwd 启动时可用)
 *   3. import.meta.dirname 的 ../.. 的 scripts(plugin 仓布局)
 *   4. process.cwd()/scripts
 */
async function resolveScriptsDir(argDir) {
  const candidates = [];
  if (argDir) candidates.push(path.resolve(argDir));
  if (process.env.PLUGIN_ROOT) candidates.push(path.join(path.resolve(process.env.PLUGIN_ROOT), 'scripts'));
  candidates.push(path.resolve(import.meta.dirname, '..', '..'));
  candidates.push(path.join(process.cwd(), 'scripts'));
  for (const c of candidates) {
    const hasPkg = await fs.access(path.join(c, 'package.json')).then(() => true).catch(() => false);
    if (hasPkg) return c;
  }
  // 兜底返回第一个候选(让 stderr 提示更明确)
  return candidates[Math.min(2, candidates.length - 1)];
}

async function checkModules(scriptsDir) {
  const modulesDir = path.join(scriptsDir, 'node_modules');
  const missing = [];
  for (const name of REQUIRED) {
    const ok = await fs.access(path.join(modulesDir, name)).then(() => true).catch(() => false);
    if (!ok) missing.push(name);
  }
  return { modulesDir, missing };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const scriptsDir = await resolveScriptsDir(args.scripts_dir);
  const { modulesDir, missing } = await checkModules(scriptsDir);

  const result = {
    ok: missing.length === 0,
    scripts_dir: scriptsDir.replace(/\\/g, '/'),
    modules_dir: modulesDir.replace(/\\/g, '/'),
    modules: REQUIRED,
  };

  if (missing.length === 0) {
    result.missing = [];
    console.log(JSON.stringify(result, null, 2));
    process.exit(0);
  } else {
    result.missing = missing;
    console.log(JSON.stringify(result, null, 2));
    console.error(`ERROR: 缺依赖 ${missing.length} 个: ${missing.join(', ')}`);
    console.error(`HINT: cd ${scriptsDir} && npm install`);
    process.exit(2);
  }
}

main().catch(err => {
  console.error(JSON.stringify({ ok: false, error: 'unexpected', message: err.message }));
  process.exit(2);
});