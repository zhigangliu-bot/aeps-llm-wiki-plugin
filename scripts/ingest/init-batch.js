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
 *   - 0.6.0: P0-#1 (issue #1) — 保留 LLM 拍板字段(slug/target_subdir/route/...):
 *     旧版 map 重写 file 会把所有 LLM 决策字段静默丢为 null,导致下游 move-to-raw
 *     fail with "target_subdir 未指定"。改为 spread LLM 输入 + 脚本必需默认值覆盖。
 *   - 0.6.5: WP-1 (issue #15) — 接受 `subdir` 作为 `target_subdir` 别名
 *     (SKILL.md 步骤 3 文档字段名与脚本字段名不一致导致 move-to-raw exit 2)。
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

  // 初始状态总线:先吃 LLM 输入的所有字段(保留拍板决策 slug/target_subdir/route/...),
  // 再补脚本必需的默认值(moved/status 等不能被 LLM 覆盖)。v0.6.0 起 issue #1 fix:
  // 旧版用 whitelist 重写 file,会把 LLM 拍板的 slug/target_subdir 静默丢为 null。
  //
  // v0.6.5 WP-1 (issue #15) 字段别名审计(SKILL.md 步骤 3 文档字段名 ↔ 脚本字段名):
  //   - `subdir`(SKILL.md 文档写法)→ `target_subdir`(下游 move-to-raw / append-log
  //     唯一认的字段名):加别名归一,归一后剔除 `subdir` 键,避免 batch 里两套字段并存。
  //   - 其余字段(path / size / ext / mtime / route / converter / native_text /
  //     converted_path / converted_emitted / slug / target_raw_path / dedupe_key)
  //     文档名 = 脚本名,经 spread 透传已一致,无同类漂移。
  const startedAt = nowIso();
  const files = inputFiles.map((f) => {
    const { subdir, ...rest } = f; // subdir 是 target_subdir 的文档别名(issue #15)
    return {
      ...rest, // 透传 LLM 决策字段(slug / target_subdir / route / converter / native_text / converted_path / 等)
      path: f.path, // 必填,覆盖可能的 null
      size: f.size || 0,
      ext: f.ext,
      mtime: f.mtime || null,
      // 脚本必需默认值(LLM 误传也覆盖)
      moved: false,
      status: 'pending',
      converted_emitted: f.converted_emitted ?? false,
      // SKILL.md 步骤 3 LLM 拍板;`subdir` 为同义别名,显式 target_subdir 优先
      target_subdir: f.target_subdir ?? subdir ?? null,
    };
  });

  const batch = {
    batch_id: batchId,
    project: project.replace(/\\/g, '/'),
    emit_dir: emitDir.replace(/\\/g, '/'),
    started_at: startedAt,
    plugin_version: '0.6.5',
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
