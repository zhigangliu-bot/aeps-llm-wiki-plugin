#!/usr/bin/env node
/**
 * convert-to-md.js — 路径 3/4 派发到 markitdown_to_md.py / ocr_to_md.py
 *
 * Usage:
 *   node scripts/ingest/convert-to-md.js --file <path> --emit-to <dir> [--json]
 *
 * 路径分流(由 classify.js 决策后传入;2026-09-18 依赖收敛):
 *   .pdf/.pptx/.docx/.xlsx/.html/.htm → markitdown/markitdown_to_md.py(统一转换,无降级链)
 *   .png/.jpg/.jpeg/.bmp/.tiff → ocr/ocr_to_md.py (paddleocr)
 *
 * 纯文本 (.md/.txt/...) 不调本脚本 (SKILL.md 直接读)
 *
 * Exit codes:
 *   0 - 成功
 *   1 - 参数错
 *   2 - spawn 失败 (non-zero exit from underlying tool)
 *   3 - 文件不存在
 *   4 - 不支持的扩展名
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { requireDeps } from '../lib/preflight.js';
await requireDeps({});

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCRIPTS_ROOT = path.resolve(__dirname, '..');

// 2026-09-18 依赖收敛:route 3 全格式统一走 MarkItDown(替换 anydoc/pyoffice/docling 链)
const MARKITDOWN_EXTS = new Set(['pdf', 'pptx', 'docx', 'xlsx', 'html', 'htm']);
const OCR_EXTS = new Set(['png', 'jpg', 'jpeg', 'bmp', 'tiff']);

function runPython(scriptAbs, args) {
  const py = process.platform === 'win32' ? 'python' : 'python3';
  return spawnSync(py, [scriptAbs, ...args], {
    encoding: 'utf8',
    windowsHide: true,
    shell: process.platform === 'win32',
  });
}

function parseArgs(argv) {
  const args = { file: null, emitTo: null, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--file') args.file = argv[++i];
    else if (a === '--emit-to') args.emitTo = argv[++i];
    else if (a === '--json') args.json = true;
  }
  if (!args.file || !args.emitTo) {
    console.error('ERROR: --file <path> 和 --emit-to <dir> 必填');
    process.exit(1);
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const file = path.resolve(args.file);
  const emitTo = path.resolve(args.emitTo);

  if (!(await fs.access(file).then(() => true).catch(() => false))) {
    console.error(`ERROR: 文件不存在: ${file}`);
    process.exit(3);
  }

  const ext = path.extname(file).toLowerCase().replace(/^\./, '');
  if (!MARKITDOWN_EXTS.has(ext) && !OCR_EXTS.has(ext)) {
    console.error(`ERROR: 不支持的扩展名: .${ext}(路径 1/2 纯文本不调本脚本)`);
    process.exit(4);
  }

  await fs.mkdir(emitTo, { recursive: true });

  const outFile = path.join(emitTo, `${path.basename(file, path.extname(file))}.md`);

  // 2026-09-18 依赖收敛:route 3 全格式统一 MarkItDown,无降级链;图片走 OCR
  const attempt = MARKITDOWN_EXTS.has(ext)
    ? { script: 'markitdown_to_md.py', run: () => runPython(path.join(SCRIPTS_ROOT, 'markitdown', 'markitdown_to_md.py'), [file, '-o', outFile]) }
    : { script: 'ocr_to_md.py', run: () => runPython(path.join(SCRIPTS_ROOT, 'ocr', 'ocr_to_md.py'), [file, '-o', outFile]) };

  const r = attempt.run();
  const scriptUsed = attempt.script;

  if (!r || r.status !== 0) {
    const errMsg = (r?.stderr || r?.stdout || `exit ${r?.status}`).toString().trim();
    console.error(`FAIL: ${scriptUsed} exit=${r?.status}: ${errMsg.slice(0, 2000)}`);
    process.exit(2);
  }

  const outStat = await fs.stat(outFile).catch(() => null);
  const result = {
    ok: true,
    script_used: scriptUsed,
    input: file.replace(/\\/g, '/'),
    output: outFile.replace(/\\/g, '/'),
    size: outStat ? outStat.size : 0,
    stdout_tail: (r.stdout || '').split('\n').slice(-3).join('\n').trim(),
  };
  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(2);
});
