#!/usr/bin/env node
/**
 * check-qmd.js — qmd 可用性探查(design.md §4.2,query 步骤 0 调用)
 *
 * Usage:
 *   node scripts/check-qmd.js --json
 *
 * 行为:
 *   - spawn `qmd --version`,超时 3s
 *   - 可用   → { "available": true, "version": "x.y.z" }
 *   - 不可用 → { "available": false }(spawn ENOENT / 超时 / 非 0 退出)
 *
 * 边界:
 *   - qmd 单独探查,**不计入 package.json 依赖清单**(design §4.4)
 *   - Windows 下 qmd 可能是 .cmd / .exe,经 shell 规避 spawn 可执行位问题;
 *     timeout 由 spawnSync 自带支持
 *   - exit 恒为 0(探查本身不是错误;"qmd 未装"由调用方按 G-Q2 / 降级策略处理)
 */

import { spawnSync } from 'node:child_process';
import process from 'node:process';

const QMD_TIMEOUT_MS = 3000;

/** 从 `qmd --version` 输出解析版本号;解析失败 fallback 首行原文 / "unknown" */
function parseVersion(stdout) {
  const text = String(stdout || '').trim();
  if (!text) return 'unknown';
  const m = text.match(/v?(\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.-]+)?)/);
  if (m) return m[1];
  return text.split(/\r?\n/)[0].trim() || 'unknown';
}

function main() {
  const wantJson = process.argv.slice(2).includes('--json');

  let res;
  try {
    res = spawnSync('qmd', ['--version'], {
      encoding: 'utf8',
      timeout: QMD_TIMEOUT_MS,
      windowsHide: true,
      // Windows 上 qmd 常以 qmd.cmd / qmd.exe 形式存在,直接 spawn 可能 ENOENT;
      // POSIX 下 shell:true 同样可用(多一层 sh 开销可接受,单次探查脚本)
      shell: process.platform === 'win32',
    });
  } catch {
    res = null;
  }

  const ok = !!res && !res.error && (res.status === 0 || res.status === null && !!res.stdout);
  if (ok) {
    const version = parseVersion(res.stdout);
    console.error(`[check-qmd] qmd 可用,version=${version}`);
    console.log(wantJson
      ? JSON.stringify({ available: true, version }, null, 2)
      : `qmd available, version=${version}`);
  } else {
    const why = !res
      ? 'spawn 异常'
      : res.error
        ? (res.error.code === 'ETIMEDOUT' ? `超时(>${QMD_TIMEOUT_MS}ms)` : res.error.code || res.error.message)
        : `exit=${res.status}${res.signal ? ` signal=${res.signal}` : ''}`;
    console.error(`[check-qmd] qmd 不可用:${why}`);
    console.log(wantJson
      ? JSON.stringify({ available: false }, null, 2)
      : 'qmd not available');
  }
  process.exit(0);
}

main();
