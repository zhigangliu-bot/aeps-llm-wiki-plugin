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
 *     #59 起默认用 pdftotext 实抽前几页验证:扫描版/图片型 PDF(抽不到文本)或抽取失败
 *     (损坏/加密/非 PDF)→ 自动降级路径 3;显式 --route 2 可跳过内容探测强制原生读
 *   路径 3 (.pptx/.docx/.xlsx/.pdf 失败时/.html):
 *     全部 → markitdown(2026-09-18 依赖收敛,替换 anydoc/pyoffice/docling 链), native_text=false, converted_path 模板
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
import { requireDeps } from '../lib/preflight.js';
await requireDeps({});

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
  // 路径 2 (PDF 原生可读 — 表值只是默认,#59 起由 probePdfText 实抽文本后可降级 path 3)
  pdf:      { route: 2, converter: 'claude-native',  native_text: true,  converted: false },
  // 路径 3 (2026-09-18 依赖收敛:全格式统一 markitdown,替换 anydoc/pyoffice/docling 链)
  pptx:     { route: 3, converter: 'markitdown',     native_text: false, converted: true },
  docx:     { route: 3, converter: 'markitdown',     native_text: false, converted: true },
  xlsx:     { route: 3, converter: 'markitdown',     native_text: false, converted: true },
  html:     { route: 3, converter: 'markitdown',     native_text: false, converted: true },
  htm:      { route: 3, converter: 'markitdown',     native_text: false, converted: true },
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
  // Windows shell:true 下 -c 参数必须自带双引号,否则整段被拆散
  const r = spawnSync(py, ['-c', '"import paddleocr"'], {
    encoding: 'utf8',
    windowsHide: true,
    shell: process.platform === 'win32',
  });
  return r.status === 0;
}

/**
 * 探查 markitdown(pip 包)是否可用 — route 3 唯一转换器
 */
function checkMarkitdown() {
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const r = spawnSync(py, ['-c', '"import markitdown"'], {
    encoding: 'utf8',
    windowsHide: true,
    shell: process.platform === 'win32',
  });
  return r.status === 0;
}

/**
 * 探查 poppler(pdftotext)是否可用 — Claude Code Read 工具读 PDF 的系统依赖(#50)
 * 结果按进程缓存(探测一次即够);缺失 → PDF 不走 route 2,直接降级 route 3
 */
let _popplerOk = null;
function checkPoppler() {
  if (_popplerOk !== null) return _popplerOk;
  // 不用 shell:shell 模式下找不到命令 exit 1 而非 ENOENT,无法与真失败区分;
  // pdftotext.exe 是普通可执行文件,无 shell 也能被 PATH 解析
  const r = spawnSync('pdftotext', ['-v'], {
    encoding: 'utf8',
    windowsHide: true,
  });
  // pdftotext -v 正常时往 stderr 打版本、exit 0 或 99;spawn 不到 → error ENOENT
  _popplerOk = !r.error;
  return _popplerOk;
}

// #59:PDF 原生文本探测参数 — 抽样前几页、每页有效字符数阈值
// (按页计:短文本真 PDF(如单页只有几十字)不该被误杀,扫描版每页几乎抽不到字符)
const PDF_PROBE_PAGES = 3;
const PDF_PROBE_MIN_CHARS_PER_PAGE = 10;

/**
 * 实抽 PDF 文本探测(#59)— 扫描版/图片型 PDF 的元数据也会自称可读,
 * 只看扩展名/元数据会误判 native_text:true,后续原生读取拿到空内容。
 * 用 pdftotext 抽前 N 页到 stdout,剥掉空白后按「有效字符数 / 实抽页数」判断:
 *   - 抽取成功且每页字符数达标 → { ok: true, ... } 可走 route 2
 *   - 抽取失败(损坏/加密/非 PDF)或每页字符数低于阈值(扫描版)→ 不可原生读
 * 不用 shell:含空格路径会被 shell 拆参;args 数组原样传递即可
 */
function probePdfText(file) {
  const r = spawnSync('pdftotext', ['-f', '1', '-l', String(PDF_PROBE_PAGES), file, '-'], {
    encoding: 'utf8',
    windowsHide: true,
    maxBuffer: 10 * 1024 * 1024,
  });
  if (r.error) {
    return { ok: false, chars: 0, pages: 0 };
  }
  const stdout = r.stdout || '';
  const chars = stdout.replace(/\s+/g, '').length;
  // 按换页符推实际抽到的页数(PDF 总页数可能不足 PDF_PROBE_PAGES;末页后的 \f 不多算一页)
  const ff = (stdout.match(/\f/g) || []).length;
  const pages = Math.max(1, Math.min(PDF_PROBE_PAGES, stdout.endsWith('\f') ? ff : ff + 1));
  return { ok: r.status === 0, chars, pages };
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
  if (ext === 'pdf' && opts.routeOverride === 3) {
    result.route = 3;
    result.converter = 'markitdown';
    result.native_text = false;
    result.converted_path = buildConvertedPath(file, opts.subdir);
    result.note = 'route 2 探测失败 → 降级 route 3 (markitdown)';
  }

  // #50:poppler 缺失时 Read 读不了 PDF,route 2 自动降级 route 3(不再赌扩展名)
  if (ext === 'pdf' && result.route === 2 && !opts.skipDepCheck && !checkPoppler()) {
    result.route = 3;
    result.converter = 'markitdown';
    result.native_text = false;
    result.converted_path = buildConvertedPath(file, opts.subdir);
    result.note = 'poppler (pdftotext) 不可用 → route 2 (claude-native) 自动降级 route 3 (markitdown);装 poppler 可恢复原生读取(Windows: winget install poppler)';
  }

  // #59:poppler 可用还需实抽文本验证 — 只凭扩展名/元数据会把扫描版 PDF 误判 native_text:true;
  // 每页有效字符数低于阈值(扫描版/图片型)或抽取失败(损坏/加密)→ 降级 route 3
  // (显式 --route 2 = 用户确认走原生读,跳过本探测;与 --route 3 显式覆盖对称)
  if (ext === 'pdf' && result.route === 2 && opts.routeOverride !== 2 && !opts.skipDepCheck) {
    const probe = probePdfText(file);
    const minChars = probe.pages * PDF_PROBE_MIN_CHARS_PER_PAGE;
    if (!probe.ok || probe.chars < minChars) {
      result.route = 3;
      result.converter = 'markitdown';
      result.native_text = false;
      result.converted_path = buildConvertedPath(file, opts.subdir);
      result.note = probe.ok
        ? `#59 PDF 抽样 ${probe.pages} 页仅抽出 ${probe.chars} 个有效字符(< 每页 ${PDF_PROBE_MIN_CHARS_PER_PAGE})→ 判定扫描版/图片型,route 2 降级 route 3 (markitdown)`
        : `#59 pdftotext 抽取失败(损坏/加密/非 PDF)→ route 2 降级 route 3 (markitdown)`;
    }
  }

  // 路径 4:paddleocr 强依赖,缺则 FAIL(对齐 G6 + implement-ingest.md §1.1)
  if (map.route === 4 && !opts.skipDepCheck && !checkPaddleocr()) {
    result.error = 'paddleocr 未安装;路径 4 必须装 paddleocr (FAIL 不降级 Python 常驻;G6)';
    result.fail = true;
    return result;
  }

  // 路径 3 markitdown 依赖:route 3 唯一转换器,缺失 FAIL
  if (result.route === 3 && opts.checkDeps && !checkMarkitdown()) {
    result.error = 'markitdown 未安装;路径 3 必须装(pip install markitdown)';
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
