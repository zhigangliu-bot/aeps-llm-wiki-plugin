#!/usr/bin/env node
/**
 * classify.js — 按扩展名 → 5 路径分流
 *
 * Usage:
 *   node scripts/ingest/classify.js --file <path> [--json]
 *   node scripts/ingest/classify.js --batch <json-path> [--json]
 *
 * 路径分流表(对齐 doc/design/implement-ingest.md §1.1 + design.md §3.2):
 *   路径 0 (.ppt/.doc/.xls):  LibreOffice headless 归一化 → 回到 1/2/3
 *   路径 1 (.md/.markdown/.rst/.txt/.csv/.json/.yaml/.yml/.xml/.html/.htm):
 *     converter=null, native_text=true, converted_path=null, 不调 convert-to-md
 *   路径 2 (.pdf Claude Code 原生可读): converter=claude-native, native_text=true, converted_path=null
 *   路径 3 (.pptx/.docx/.xlsx/.pdf 失败时/.html):
 *     pdf→anydoc, pptx/docx/xlsx→docling, html→anydoc, native_text=false, converted_path 模板
 *   路径 4 (.png/.jpg/.jpeg/.bmp/.tiff): paddleocr 强依赖, 缺则 FAIL 不降级
 *
 * Exit codes:
 *   0 - 成功(单文件 / 批量)
 *   1 - 参数错
 *   2 - 路径 4 paddleocr 缺失 (FAIL,不降级)
 *   3 - 文件不存在
 *   4 - 未知扩展名
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';

const PATH_MAP = {
  // 路径 0 (老格式,convert-to-md.js 走 LibreOffice 预归一化)
  ppt: { route: 0, converter: 'libreoffice', native_text: false, converted: true },
  doc: { route: 0, converter: 'libreoffice', native_text: false, converted: true },
  xls: { route: 0, converter: 'libreoffice', native_text: false, converted: true },
  // 路径 1 (纯文本)
  md:       { route: 1, converter: null,             native_text: true,  converted: false },
  markdown: { route: 1, converter: null,             native_text: true,  converted: false },
  rst:      { route: 1, converter: null,             native_text: true,  converted: false },
  txt:      { route: 1, converter: null,             native_text: true,  converted: false },
  csv:      { route: 1, converter: null,             native_text: true,  converted: false },
  json:     { route: 1, converter: null,             native_text: true,  converted: false },
  yaml:     { route: 1, converter: null,             native_text: true,  converted: false },
  yml:      { route: 1, converter: null,             native_text: true,  converted: false },
  xml:      { route: 1, converter: null,             native_text: true,  converted: false },
  // 路径 2 (PDF 原生可读 — 由 SKILL.md 探测后覆盖为 path 3 若失败)
  pdf:      { route: 2, converter: 'claude-native',  native_text: true,  converted: false },
  // 路径 3 (docx/pptx/xlsx → docling; pdf 失败 / html → anydoc)
  pptx:     { route: 3, converter: 'docling',        native_text: false, converted: true },
  docx:     { route: 3, converter: 'docling',        native_text: false, converted: true },
  xlsx:     { route: 3, converter: 'docling',        native_text: false, converted: true },
  html:     { route: 3, converter: 'anydoc',         native_text: false, converted: true },
  htm:      { route: 3, converter: 'anydoc',         native_text: false, converted: true },
  // 路径 4 (OCR 强依赖 paddleocr)
  png:      { route: 4, converter: 'paddleocr',      native_text: false, converted: true },
  jpg:      { route: 4, converter: 'paddleocr',      native_text: false, converted: true },
  jpeg:     { route: 4, converter: 'paddleocr',      native_text: false, converted: true },
  bmp:      { route: 4, converter: 'paddleocr',      native_text: false, converted: true },
  tiff:     { route: 4, converter: 'paddleocr',      native_text: false, converted: true },
};

function buildConvertedPath(file, subdir) {
  // 与 gen-page.js 路径一致: ./raw/{subdir}/{basename}.{ext}.converted.md
  const base = path.basename(file, path.extname(file));
  const ext = path.extname(file).toLowerCase().replace(/^\./, '');
  const sub = subdir || '';
  return `./raw/${sub}/${base}.${ext}.converted.md`;
}

/**
 * 探查 paddleocr 是否可用
 * 实现策略:`python -c "import paddleocr"` 试 import
 * 不调 pip install,失败返回 false
 */
function checkPaddleocr() {
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const r = spawnSync(py, ['-c', 'import paddleocr'], {
    encoding: 'utf8',
    windowsHide: true,
    shell: process.platform === 'win32',
  });
  return r.status === 0;
}

/**
 * 探查 docling 是否可用
 */
function checkDocling() {
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const r = spawnSync(py, ['-c', 'import docling'], {
    encoding: 'utf8',
    windowsHide: true,
    shell: process.platform === 'win32',
  });
  return r.status === 0;
}

/**
 * 探查 anydoc 是否可用
 */
function checkAnydoc() {
  const r = spawnSync(process.execPath, ['-e', "import('anydoc').then(()=>process.exit(0)).catch(()=>process.exit(1))"], {
    encoding: 'utf8',
    windowsHide: true,
  });
  return r.status === 0;
}

function classifyOne(file, opts = {}) {
  const ext = path.extname(file).toLowerCase().replace(/^\./, '');
  const map = PATH_MAP[ext];
  if (!map) {
    return {
      ext,
      path: file,
      route: null,
      converter: null,
      native_text: null,
      converted_path: null,
      error: `unknown extension: .${ext}`,
    };
  }

  const result = {
    ext,
    path: file,
    route: map.route,
    converter: map.converter,
    native_text: map.native_text,
    converted_path: map.converted ? buildConvertedPath(file, opts.subdir) : null,
  };

  // 路径 0:LibreOffice 未装 → 提示用户装(不静默降级)
  if (map.route === 0) {
    result.note = 'route 0: LibreOffice headless 预归一化(若未装 → 提示用户)';
  }

  // 路径 3 PDF:SKILL.md 默认建议 path 2 (claude-native),SKILL.md 步骤 0 探测后用 --route 3 覆盖
  // 这里默认就是 route 2,SKILL.md 步骤 0 失败时显式 --route 3 重新跑
  if (ext === 'pdf' && opts.routeOverride) {
    const target = opts.routeOverride;
    if (target === 3) {
      result.route = 3;
      result.converter = 'anydoc';
      result.native_text = false;
      result.converted_path = buildConvertedPath(file, opts.subdir);
      result.note = 'route 2 探测失败 → 降级 route 3 (anydoc)';
    }
  }

  // 路径 4:paddleocr 强依赖,缺则 FAIL(对齐 G6 + implement-ingest.md §1.1)
  if (map.route === 4 && !opts.skipDepCheck && !checkPaddleocr()) {
    result.error = 'paddleocr 未安装;路径 4 必须装 paddleocr (FAIL 不降级 Python 常驻;G6)';
    result.fail = true;
    return result;
  }

  // 路径 3 docling 依赖:若 SKILL.md 调用时 --check-deps 可探查
  if ((ext === 'pptx' || ext === 'docx' || ext === 'xlsx') && opts.checkDeps && !checkDocling()) {
    result.error = 'docling 未安装;路径 3 (docx/pptx/xlsx) 必须装 docling';
    result.fail = true;
    return result;
  }

  // 路径 3 anydoc 依赖:若需要
  if ((ext === 'html' || ext === 'htm' || (ext === 'pdf' && result.route === 3)) && opts.checkDeps && !checkAnydoc()) {
    result.error = 'anydoc 未安装;路径 3 (pdf/html) 必须装 @firecrawl/anydoc';
    result.fail = true;
    return result;
  }

  return result;
}

async function classifyBatch(batchPath, routeOverride = null) {
  const txt = await fs.readFile(batchPath, 'utf8');
  const batch = JSON.parse(txt);
  const opts = {
    subdir: null,
    routeOverride,
    skipDepCheck: false,
    checkDeps: false,
  };
  const results = [];
  for (const entry of batch.files || []) {
    const r = classifyOne(entry.path, opts);
    results.push({ ...entry, classify: r });
  }
  return { batch_id: batch.batch_id, results };
}

function parseArgs(argv) {
  const args = { file: null, batch: null, subdir: null, json: false, checkDeps: false, route: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--file') args.file = argv[++i];
    else if (a === '--batch') args.batch = argv[++i];
    else if (a === '--subdir') args.subdir = argv[++i];
    else if (a === '--json') args.json = true;
    else if (a === '--check-deps') args.checkDeps = true;
    else if (a === '--route') {
      // 显式覆盖 route(只接受 2 或 3);非法值 → exit 1
      const r = argv[++i];
      if (r !== '2' && r !== '3') {
        console.error(`ERROR: --route 只接受 2 或 3,收到 ${r}`);
        process.exit(1);
      }
      args.route = Number(r);
    }
  }
  if (!args.file && !args.batch) {
    console.error('ERROR: 必须传 --file <path> 或 --batch <batch.json>');
    process.exit(1);
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.batch) {
    const out = await classifyBatch(args.batch, args.route);
    console.log(JSON.stringify(out, null, 2));
    process.exit(0);
  } else {
    // 单文件模式
    const file = path.resolve(args.file);
    if (!(await fs.access(file).then(() => true).catch(() => false))) {
      console.error(`ERROR: 文件不存在: ${file}`);
      process.exit(3);
    }
    const result = classifyOne(file.replace(/\\/g, '/'), {
      subdir: args.subdir,
      checkDeps: args.checkDeps,
      routeOverride: args.route,
    });
    console.log(JSON.stringify(result, null, 2));
    if (result.fail) {
      process.exit(2);
    }
    process.exit(0);
  }
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(2);
});
