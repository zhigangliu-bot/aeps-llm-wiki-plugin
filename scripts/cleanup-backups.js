#!/usr/bin/env node
/**
 * cleanup-backups.js — 清理 temp/raw_backup_<pattern> 过期目录(PR-D,修复 issue #27)
 *
 * Usage:
 *   node scripts/cleanup-backups.js --temp <dir> [--days N] [--apply] [--json]
 *
 * 行为:
 *   - 默认 --dry-run:只输出每个 backup 的 [would-delete] / [skip] 决策,不真删
 *   - 加 --apply:才 rmSync 过期目录
 *   - --days N:TTL 阈值(默认 7);过期 = date < now - days × 86400s
 *   - 兼容两种目录命名:
 *       1. 新格式:raw_backup_{YYYY-MM-DD}_{hash}/     → 按日期前缀解析
 *       2. 旧格式:raw_backup_{hash}/                  → 用 mtime 推断日期(v0.6.6 存量)
 *   - --temp <dir>:扫描根目录(默认 ./temp)
 *   - --json:stdout 输出结构化 JSON,便于 SKILL.md / 其它脚本消费
 *
 * Exit codes:
 *   0 - 成功(无论有没有删)
 *   1 - 参数错
 *
 * > **change history**(本文件 v0.6.x 起每次变更追加一行):
 * > - **v0.6.6 (PR-D)** — 新建,清理 temp/raw_backup_<pattern> 过期目录(issue #27);
 *   默认 --dry-run + --apply 才真删;--days N 改 TTL(默认 7);兼容旧格式(无日期前缀)用 mtime 推断;
 *   --json 输出结构化;--temp 支持任意路径。
 */

import { existsSync, readdirSync, statSync, rmSync } from 'node:fs';
import { resolve, join } from 'node:path';

// ponytail: 严格匹配 YYYY-MM-DD 前缀;不依赖 chrono / date-fns
const DATE_PREFIX_RE = /^raw_backup_(\d{4}-\d{2}-\d{2})_([a-f0-9]+)$/;
// 旧格式 fallback:v0.6.6 存量目录无日期前缀
const LEGACY_RE = /^raw_backup_([a-f0-9]+)$/;

function parseBackupDate(name, stat) {
  const m = name.match(DATE_PREFIX_RE);
  if (m) return new Date(m[1] + 'T00:00:00Z');
  const legacy = name.match(LEGACY_RE);
  if (legacy) return stat.mtime; // 旧格式用 mtime 推断
  return null;
}

function listBackups(tempDir) {
  if (!existsSync(tempDir)) return [];
  return readdirSync(tempDir)
    .filter((d) => d.startsWith('raw_backup_'))
    .map((d) => {
      const full = join(tempDir, d);
      try {
        const stat = statSync(full);
        if (!stat.isDirectory()) return null;
        const date = parseBackupDate(d, stat);
        if (!date) return null;
        return { name: d, path: full, date };
      } catch { return null; }
    })
    .filter(Boolean);
}

function parseArgs(argv) {
  const args = { temp: null, days: 7, apply: false, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--temp') args.temp = argv[++i];
    else if (a === '--days') {
      const n = parseInt(argv[++i], 10);
      if (!Number.isFinite(n) || n < 0) {
        console.error('ERROR: --days 必须是 ≥0 整数');
        process.exit(1);
      }
      args.days = n;
    }
    else if (a === '--apply') args.apply = true;
    else if (a === '--json') args.json = true;
    else if (a === '--help' || a === '-h') {
      console.log('Usage: node cleanup-backups.js --temp <dir> [--days N] [--apply] [--json]');
      process.exit(0);
    } else {
      console.error(`ERROR: 未知参数 "${a}"`);
      process.exit(1);
    }
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const tempDir = resolve(args.temp || './temp');
  const cutoff = Date.now() - args.days * 86_400_000;
  const dryRun = !args.apply;

  const backups = listBackups(tempDir);
  const decisions = [];

  for (const b of backups) {
    const ageMs = Date.now() - b.date.getTime();
    const expired = b.date.getTime() < cutoff;
    let action;
    if (expired) action = dryRun ? 'would-delete' : 'deleted';
    else action = 'skip';
    decisions.push({
      name: b.name,
      date: b.date.toISOString().slice(0, 10),
      age_days: Math.floor(ageMs / 86_400_000),
      action,
    });
    if (expired && !dryRun) {
      rmSync(b.path, { recursive: true, force: true });
    }
  }

  if (args.json) {
    console.log(JSON.stringify({
      temp: tempDir,
      ttl_days: args.days,
      dry_run: dryRun,
      scanned: backups.length,
      decisions,
    }, null, 2));
    return;
  }

  console.log(`scanned ${backups.length} backup(s) in ${tempDir} (TTL: ${args.days} days${dryRun ? ', dry-run' : ', apply'})`);
  for (const d of decisions) {
    console.log(`  [${d.action}] ${d.name} (${d.age_days}d old)`);
  }
  if (dryRun) console.log(`\n(dry-run) 加 --apply 才会真删`);
}

main();
