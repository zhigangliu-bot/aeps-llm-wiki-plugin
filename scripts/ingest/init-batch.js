#!/usr/bin/env node
/**
 * init-batch.js — 创建 temp/ingest-batch-{ts}.json 状态总线
 *
 * Usage:
 *   node scripts/ingest/init-batch.js --project <dir> --files <json> --emit-dir <dir> [--json]
 *   node scripts/ingest/init-batch.js --project <dir> --files-file <absolute> --emit-dir <dir> [--json]
 *
 * --files 与 --files-file 互斥(二选一):
 *   --files <json>          JSON 字符串(数组,文件少时内联)
 *     例如 '[{"path":"inbox/foo.pdf","size":1024,"ext":"pdf","mtime":"2026-09-07T10:00:00Z"}]'
 *   --files-file <absolute> 从文件读 JSON(文件多 / 路径长 / 含特殊字符时)
 *     文件内容必须是 JSON 数组,格式与 --files 内联字符串一致
 *
 * 输出:
 *   { batch_id, batch_file: temp/ingest-batch-{ts}.json, files: [...], started_at }
 *
 * 后续 4 个脚本 (move-to-raw / build-related-pages / append-log / lint) 读这个文件共享状态
 *
 * Exit codes:
 *   0 - 成功
 *   1 - 参数错(互斥 / 缺参 / JSON 解析失败)
 *   2 - 写盘失败 / 缺依赖
 *
 * change history:
 *   - 0.5.6: P1-3 --files-file 互斥校验(批次 3)
 *   - 0.5.6: inline preflight(批次 3)
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { requireDeps } from '../lib/preflight.js';
// init-batch.js 不依赖 js-yaml/ajv;inline preflight 用空对象(只校验未来扩展)
await requireDeps({});

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function tsForFilename() {
  // 文件名安全版本:2026-09-07T10-00-00Z
  return nowIso().replace(/:/g, '-');
}

async function readFilesArg(arg, isFile) {
  // P1-3: --files 内联 JSON 字符串 OR --files-file 文件路径
  // isFile=true → 强制当文件读(用于 --files-file);isFile=false → 自动探测(用于 --files)
  if (isFile) {
    const txt = await fs.readFile(arg, 'utf8');
    return JSON.parse(txt);
  }
  // --files 自动探测:以 [ 开头 → JSON 字符串;否则 → 文件路径
  const trimmed = arg.trim();
  if (trimmed.startsWith('[')) {
    return JSON.parse(trimmed);
  }
  const txt = await fs.readFile(arg, 'utf8');
  return JSON.parse(txt);
}

function parseArgs(argv) {
  const args = { project: null, files: null, filesFile: null, emitDir: null, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--files') args.files = argv[++i];
    else if (a === '--files-file') args.filesFile = argv[++i];
    else if (a === '--emit-dir') args.emitDir = argv[++i];
    else if (a === '--json') args.json = true;
  }

  // P1-3 互斥校验:--files 与 --files-file 二选一(都不传或都传都 ERROR)
  const hasFiles = args.files !== null;
  const hasFilesFile = args.filesFile !== null;
  if (hasFiles && hasFilesFile) {
    console.error('ERROR: --files 与 --files-file 互斥,二选一');
    console.error('HINT: 文件少 → --files \'<json>\'  ;文件多 → --files-file <absolute>');
    process.exit(1);
  }
  if (!hasFiles && !hasFilesFile) {
    console.error('ERROR: --files 与 --files-file 至少传一个');
    process.exit(1);
  }
  if (!args.project || !args.emitDir) {
    console.error('ERROR: --project / --emit-dir 都必填');
    process.exit(1);
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const project = path.resolve(args.project);
  const emitDir = path.resolve(args.emitDir);
  // P1-3: 二选一源:--files 内联字符串 OR --files-file 文件路径
  const source = args.files !== null ? args.files : args.filesFile;
  const isFile = args.filesFile !== null;
  const inputFiles = await readFilesArg(source, isFile);

  // 状态文件:temp/ingest-batch-{ts}.json
  const tempDir = path.join(project, 'temp');
  await fs.mkdir(tempDir, { recursive: true });

  const ts = tsForFilename();
  const batchId = `ingest-batch-${ts}`;
  const batchFile = path.join(tempDir, `${batchId}.json`);

  // 初始状态总线:每个文件预填入 path/size/ext/mtime,留空字段由后续脚本填
  const startedAt = nowIso();
  const files = inputFiles.map((f) => ({
    path: f.path,
    size: f.size || 0,
    ext: f.ext,
    mtime: f.mtime || null,
    // 由 classify.js 填
    route: null,
    converter: null,
    native_text: null,
    // 由 SKILL.md 步骤 3 填
    target_subdir: null,
    // 由 move-to-raw.js 填
    target_raw_path: null,
    converted_path: null,
    converted_emitted: false,
    moved: false,
    status: 'pending',
  }));

  const batch = {
    batch_id: batchId,
    project: project.replace(/\\/g, '/'),
    emit_dir: emitDir.replace(/\\/g, '/'),
    started_at: startedAt,
    plugin_version: '0.6.0',
    files,
  };

  try {
    await fs.writeFile(batchFile, JSON.stringify(batch, null, 2), 'utf8');
  } catch (e) {
    console.error(`ERROR: 写 batch 文件失败: ${batchFile}: ${e.message}`);
    process.exit(2);
  }

  const result = {
    batch_id: batchId,
    batch_file: batchFile.replace(/\\/g, '/'),
    project: project.replace(/\\/g, '/'),
    started_at: startedAt,
    file_count: files.length,
  };
  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(2);
});
