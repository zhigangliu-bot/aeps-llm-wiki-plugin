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
 *   - 0.6.8 (issue #25 fix, PR-C):新增 `normalizeFileEntry(raw)` 函数 ——
 *     接受 `path` / `source_path` / `file_path` / `file` 4 种路径字段名别名
 *     (SKILL.md 步骤 3 文档字段名 ↔ 脚本字段名漂移,导致 v0.6.8 ERR_INVALID_ARG_TYPE 回归);
 *     优先级:path > source_path > file_path > file;归一后剔除非规范键,避免 batch 里两套字段并存
 *     导致下游 move-to-raw 读 file.path 拿到 undefined。
 *     同步支持:`ext` / `file_ext` / `path.extname` · `subdir` / `target_subdir` ·
 *     `slug` / `source_slug` · `route` · `entities` / `concepts` 透传。
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

/**
 * v0.6.8 (issue #25 fix, PR-C):把 LLM 在 batch.json 中写的"任意写法"统一归一为脚本权威字段。
 *
 * 接受多种字段名别名(优先级 = 排序):
 *   - `path` > `source_path` > `file_path` > `file`         (路径,必有)
 *   - `ext` > `file_ext` > `path.extname(path)`             (扩展名)
 *   - `subdir` > `target_subdir`                             (raw 子目录,SKILL.md 别名)
 *   - `slug` > `source_slug`                                 (知识页 slug,SKILL.md 别名)
 *   - `route` / `converter` / `native_text` / `converted_path` /
 *     `converted_emitted` / `mtime` / `size` / `entities` / `concepts`
 *     等字段透传(原值,不做归一)
 *
 * 归一后剔除非规范键(source_path / file_path / file / file_ext /
 * source_slug),避免下游脚本读 file.path 时与 file.source_path
 * 同时存在导致歧义。
 *
 * 抛出:
 *   - batch entry 非对象 → Error('batch entry 必须是对象,...')
 *   - 路径字段全部缺失 → Error('batch entry 缺路径字段(接受 path / source_path / ...);actual keys: ...')
 */
export function normalizeFileEntry(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error(`batch entry 必须是对象,实际: ${typeof raw} ${JSON.stringify(raw)}`);
  }
  const pathVal = raw.path ?? raw.source_path ?? raw.file_path ?? raw.file;
  if (!pathVal || typeof pathVal !== 'string') {
    throw new Error(
      `batch entry 缺路径字段(接受 path / source_path / file_path / file);` +
      `actual keys: ${Object.keys(raw).join(', ')}`
    );
  }
  const extVal = raw.ext ?? raw.file_ext ?? path.extname(pathVal);
  // 优先级:target_subdir > subdir(显式权威字段 > 别名),与 v0.6.5 WP-1 一致
  const subdirVal = raw.target_subdir ?? raw.subdir ?? null;
  // 优先级:slug > source_slug(显式权威字段 > 别名)
  const slugVal = raw.slug ?? raw.source_slug ?? null;

  // 剔除非规范键,避免下游歧义;其他 LLM 字段透传
  const dropKeys = new Set(['source_path', 'file_path', 'file', 'file_ext', 'source_slug', 'target_subdir', 'subdir']);
  const rest = {};
  for (const [k, v] of Object.entries(raw)) {
    if (!dropKeys.has(k)) rest[k] = v;
  }

  return {
    ...rest,
    path: pathVal,
    ext: extVal,
    target_subdir: subdirVal,
    slug: slugVal,
  };
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
  //
  // v0.6.8 (issue #25 fix, PR-C):`normalizeFileEntry` 把 LLM 任意写法
  //   (path / source_path / file_path / file 四种路径字段名别名)归一为权威字段;
  //   下游 move-to-raw 读 file.path 不再拿到 undefined。
  const startedAt = nowIso();
  const normalizedFiles = inputFiles.map((f) => {
    try {
      return normalizeFileEntry(f);
    } catch (e) {
      console.error(`ERROR: ${e.message}`);
      process.exit(1);
    }
  });
  const files = normalizedFiles.map((f) => ({
    ...f,
    size: f.size || 0,
    mtime: f.mtime || null,
    // 脚本必需默认值(LLM 误传也覆盖)
    moved: false,
    status: 'pending',
    converted_emitted: f.converted_emitted ?? false,
  }));

  const batch = {
    batch_id: batchId,
    project: project.replace(/\\/g, '/'),
    emit_dir: emitDir.replace(/\\/g, '/'),
    started_at: startedAt,
    plugin_version: '0.6.8',
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
