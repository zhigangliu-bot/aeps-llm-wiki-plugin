#!/usr/bin/env node
/**
 * move-to-raw.js — 替代 safe-mv.py (PRD §4.2 步骤 4)
 *
 * Usage:
 *   node scripts/ingest/move-to-raw.js --project <dir> --batch <batch.json> [--apply] [--json]
 *
 * 行为:
 *   1. 读 batch.json files[] (含 target_subdir 由 SKILL.md 步骤 3 填入)
 *   2. 每个文件:
 *      a. 若 raw/{subdir}/{file} 已存在同名 → 强制拍板门 (y/n/d) — 由 SKILL.md 在调用前设置 --decision
 *         [y] 覆盖 (先备份到 temp/raw_backup_{hash}/ + os.replace() 原子替换)
 *         [n] 跳过 (status: skipped, inbox 文件保留)
 *         [d] 仅删旧副本 (status: deleted-old)
 *      b. 同时迁原文件 + .converted.md (若有)
 *      c. 删除 inbox 原文件
 *   3. dry-run 默认 (只输出 diff);--apply 才写盘
 *
 * --decision y|n|d (apply 模式才需要;SKILL.md 拍板后传入)
 *
 * Exit codes:
 *   0 - 成功
 *   1 - 参数错
 *   2 - 未指定 --decision 且有冲突
 *   3 - 写盘失败
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import crypto from 'node:crypto';

async function exists(p) {
  try { await fs.access(p); return true; } catch { return false; }
}

async function readJson(p) {
  const txt = await fs.readFile(p, 'utf8');
  return JSON.parse(txt);
}

function sha256Short(s) {
  return crypto.createHash('sha256').update(s).digest('hex').slice(0, 8);
}

function parseArgs(argv) {
  const args = { project: null, batch: null, apply: false, decision: null, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--batch') args.batch = argv[++i];
    else if (a === '--apply') args.apply = true;
    else if (a === '--decision') args.decision = argv[++i];
    else if (a === '--json') args.json = true;
  }
  if (!args.project || !args.batch) {
    console.error('ERROR: --project / --batch 必填');
    process.exit(1);
  }
  if (args.decision && !['y', 'n', 'd'].includes(args.decision)) {
    console.error('ERROR: --decision 必须是 y | n | d');
    process.exit(1);
  }
  return args;
}

async function backupToTemp(project, subdir, file, dryRun, backedUp) {
  // 备份目录: temp/raw_backup_{hash}/
  // hash 由 subdir + filename 生成,避免冲突
  const hash = sha256Short(`${subdir}/${file}`);
  const backupDir = path.join(project, 'temp', `raw_backup_${hash}`);
  if (!dryRun) await fs.mkdir(backupDir, { recursive: true });
  const srcPath = path.join(project, 'raw', subdir, file);
  const dstPath = path.join(backupDir, file);
  if (!dryRun) {
    try { await fs.copyFile(srcPath, dstPath); } catch (e) { /* skip */ }
  }
  backedUp.push({ src: srcPath, dst: dstPath });
  return backupDir;
}

async function moveOne(project, file, decision, dryRun, result) {
  // file: { path: 'inbox/foo.pdf', target_subdir: '06_功能安全', converted_path: './raw/06_功能安全/foo.pdf.converted.md' }
  const subdir = file.target_subdir;
  if (!subdir) {
    result.failed.push({ file: file.path, reason: 'target_subdir 未指定 (SKILL.md 步骤 3 必填)' });
    return;
  }
  const inboxPath = path.join(project, 'inbox', path.basename(file.path));
  const rawDir = path.join(project, 'raw', subdir);
  const fileName = path.basename(file.path);
  const destPath = path.join(rawDir, fileName);

  // 转换副本(若有)
  const convRel = file.converted_path;
  let convDestPath = null;
  let convInboxPath = null;
  if (convRel) {
    // converted_path 是 ./raw/{subdir}/{basename}.{ext}.converted.md
    // 副本原文件路径 = inbox/{basename}.{ext}.converted.md (SKILL.md 步骤 2 转换后写入 inbox)
    const base = path.basename(file.path, path.extname(file.path));
    const ext = path.extname(file.path).toLowerCase().replace(/^\./, '');
    const convFileName = `${base}.${ext}.converted.md`;
    convInboxPath = path.join(project, 'inbox', convFileName);
    convDestPath = path.join(rawDir, convFileName);
  }

  const conflict = await exists(destPath);
  let actionTaken = 'moved';
  let backupDir = null;

  if (conflict) {
    // 强制拍板门
    if (!decision) {
      result.conflicts.push({ file: fileName, subdir, dest: destPath });
      result.failed.push({ file: file.path, reason: 'raw 已存在同名,需 --decision y/n/d' });
      return;
    }
    if (decision === 'n') {
      result.skipped.push({ file: fileName, subdir, reason: 'user chose [n] skip' });
      return;
    }
    if (decision === 'd') {
      // 仅删旧副本
      if (!dryRun) {
        await fs.rm(destPath, { force: true });
        if (convDestPath && await exists(convDestPath)) await fs.rm(convDestPath, { force: true });
      }
      actionTaken = 'deleted-old';
    } else if (decision === 'y') {
      // 先备份
      backupDir = await backupToTemp(project, subdir, fileName, dryRun, result.backed_up);
      if (convDestPath && await exists(convDestPath)) {
        await backupToTemp(project, subdir, path.basename(convDestPath), dryRun, result.backed_up);
      }
      actionTaken = 'overwritten';
    }
  }

  // 创建目标目录
  if (!dryRun) await fs.mkdir(rawDir, { recursive: true });

  // 迁原文件
  if (!dryRun) {
    try {
      await fs.copyFile(inboxPath, destPath);
      await fs.rm(inboxPath, { force: true });
    } catch (e) {
      result.failed.push({ file: file.path, reason: `mv 失败: ${e.message}` });
      return;
    }
    file.moved = true;
    file.status = actionTaken;
    file.target_raw_path = destPath.replace(/\\/g, '/');

    // 迁副本(若有)
    if (convInboxPath && convDestPath && await exists(convInboxPath)) {
      try {
        await fs.copyFile(convInboxPath, convDestPath);
        await fs.rm(convInboxPath, { force: true });
        file.converted_emitted = true;
      } catch (e) {
        // 副本迁失败不致命(原文件已迁)
        result.warnings.push({ file: fileName, reason: `.converted.md 迁失败: ${e.message}` });
      }
    }
  }

  result.moved.push({
    file: fileName,
    subdir,
    action: actionTaken,
    backup_dir: backupDir ? backupDir.replace(/\\/g, '/') : null,
    dry_run: dryRun,
  });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const project = path.resolve(args.project);
  const batch = await readJson(args.batch);
  const dryRun = !args.apply;

  const result = {
    dry_run: dryRun,
    decision: args.decision,
    moved: [],
    skipped: [],
    conflicts: [],
    backed_up: [],
    warnings: [],
    failed: [],
  };

  for (const f of batch.files) {
    await moveOne(project, f, args.decision, dryRun, result);
  }

  // 把更新后的 batch 写回 (dry-run 时也写 — 仅在内存更新;实跑时持久化以供后续脚本读)
  if (!dryRun) {
    try {
      await fs.writeFile(args.batch, JSON.stringify(batch, null, 2), 'utf8');
    } catch (e) {
      console.error(`WARN: batch.json 写回失败: ${e.message}`);
      result.warnings.push({ reason: `batch.json 写回失败: ${e.message}` });
    }
  }

  console.log(JSON.stringify(result, null, 2));

  // 退出码:失败/冲突 → 非零
  if (result.failed.length > 0 || result.conflicts.length > 0) {
    process.exit(2);
  }
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(3);
});
