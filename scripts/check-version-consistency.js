#!/usr/bin/env node
/**
 * check-version-consistency.js
 *
 * 扫描 doc/ skills/ scripts/ README.md 内出现的所有 semver 三段式版本号字串
 * (`/0.x.y/`),与 .claude-plugin/plugin.json 的 version 字段比对。
 *
 * - 不一致 → 输出 `file:line 字串` 列表 + exit 1
 * - 一致 → 输出 OK + exit 0
 *
 * 用法(手动跑):node scripts/check-version-consistency.js
 *
 * 白名单(不扫描):
 *   - 目录:.trellis/ / temp/ / node_modules/ / .git/
 *   - 文件:package-lock.json / CHANGELOG.md
 *   - 路径前缀:`scripts/test/` `scripts/ingest/test/` `scripts/init/test/`
 *     `scripts/update-check/test/`(测试 fixture 故意 hardcode 老版本)
 *   - 路径前缀:`scripts/update-check/`(子包自身有自己的版本号 + 测试
 *     字符串,跟 plugin 主版本号解耦)
 *   - `scripts/package.json` / `scripts/update-check/package.json`(子包
 *     version 字段与 plugin 主版本号解耦)
 *   - 本脚本自身
 *
 * 不引入 npm 依赖,只用 node:fs / node:path / node:url。
 *
 * 注意:历史 Change History 表格里的旧版本字串(如 `| 0.5.2 | 2026-09-04 | 初版`)
 * 是合法的"历史快照",不应作为不一致报错。本脚本扫描这些表格时按
 * 「整行只含表格分隔符 + 版本字串」的格式不报(简化处理:不扫
 * 含 `|` 表格分隔符的行)。
 *
 * 同时跳过依赖版本声明行(含 `^` / `~` / `>=` 等 npm 语法),这些是
 * 第三方包版本,跟 plugin 主版本号解耦。
 */

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const PLUGIN_ROOT = path.resolve(
  path.dirname(url.fileURLToPath(import.meta.url)),
  '..',
);
const PLUGIN_JSON = path.join(PLUGIN_ROOT, '.claude-plugin', 'plugin.json');

const SCAN_ROOTS = ['doc', 'skills', 'scripts'];
const SCAN_FILES = ['README.md'];
const SKIP_DIRS = new Set(['.trellis', 'temp', 'node_modules', '.git']);
const SKIP_FILES = new Set([
  'package-lock.json',
  'CHANGELOG.md',
  path.basename(url.fileURLToPath(import.meta.url)),
]);
// 路径前缀白名单:相对 PLUGIN_ROOT,统一用 POSIX 分隔符判断
const SKIP_PATH_PREFIXES = [
  'scripts/test/',
  'scripts/ingest/test/',
  'scripts/init/test/',
  'scripts/update-check/',
];
const SKIP_PACKAGE_JSON = new Set([
  'scripts/package.json',
  'scripts/update-check/package.json',
]);

const VERSION_RE = /\b0\.[0-9]+\.[0-9]+\b/g;

function readPluginVersion() {
  const raw = readFileSync(PLUGIN_JSON, 'utf8');
  const obj = JSON.parse(raw);
  if (typeof obj.version !== 'string' || !/^\d+\.\d+\.\d+$/.test(obj.version)) {
    throw new Error(
      `plugin.json 的 version 字段不是合法 semver 三段式:${obj.version}`,
    );
  }
  return obj.version;
}

function shouldSkipByPath(relPosix) {
  const base = path.posix.basename(relPosix);
  if (SKIP_FILES.has(base)) return true;
  if (SKIP_PACKAGE_JSON.has(relPosix)) return true;
  for (const pfx of SKIP_PATH_PREFIXES) {
    if (relPosix.startsWith(pfx)) return true;
  }
  return false;
}

function listFiles(rootAbs) {
  const out = [];
  const stack = [rootAbs];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch (e) {
      continue;
    }
    for (const ent of entries) {
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        if (SKIP_DIRS.has(ent.name)) continue;
        stack.push(full);
      } else if (ent.isFile()) {
        const rel = path.relative(PLUGIN_ROOT, full).replace(/\\/g, '/');
        if (shouldSkipByPath(rel)) continue;
        out.push(full);
      }
    }
  }
  return out;
}

function scanFile(absPath, expectedVersion) {
  const findings = [];
  let content;
  try {
    content = readFileSync(absPath, 'utf8');
  } catch (e) {
    return findings;
  }
  const lines = content.split(/\r?\n/);
  // 跟踪当前是否在白名单段落内(Change History / Plugin Version Note 等叙述段)
  let inSkipBlock = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // 跳过表格行(Change History 等历史快照,旧版本字串合法)
    if (/^\s*\|/.test(line)) continue;
    // 跳过依赖版本声明行(含 `^` / `~` / `>=` / `<=` 等 npm 依赖语法的行;
    // 这些是第三方包版本,不是 plugin 主版本)
    if (/[`^~]\s*0\.\d+\.\d+/.test(line)) continue;
    if (/>=\s*0\.\d+\.\d+/.test(line)) continue;
    if (/<=\s*0\.\d+\.\d+/.test(line)) continue;
    // 跳过 cache 路径示例(如 ~/.claude/plugins/cache/.../0.5.6/):
    // 这些是叙述性历史路径引用,不是当前 active 版本声明
    if (/\.claude\/plugins\/cache\/[^/]+\/[^/]+\/0\.\d+\.\d+/.test(line)) continue;
    // 跳过脚本 / 文档顶部的 JSDoc / 注释式 change history 列表项:
    //   * - 0.5.6: ...   ← 这种是历史版本变更叙述,合法保留
    //   // - 0.5.6: ...  ← 脚本注释里的版本说明,合法保留
    if (/^\s*(\*|\/\/|#)\s*[-]?\s*0\.\d+\.\d+:/.test(line)) continue;
    // 跳过 Change History / Plugin Version Note 等叙述段落:
    // 进入条件:行内含 "## Change History" / "## Plugin Version Note" 标题(忽略前导 # / 空白)
    // 退出条件:下一个 ## 开头的标题
    if (/^#{1,6}\s+/.test(line)) {
      inSkipBlock = /Change History|Plugin Version Note/.test(line);
      continue;
    }
    if (inSkipBlock) continue;
    // 只检查"明确的版本声明语境"——行内必须出现下列 keyword 之一:
    //   - plugin-version: / plugin_version: / PLUGIN_VERSION
    //   - **plugin 版本** / plugin 版本
    //   - producer/aeps-llm-wiki-plugin/<ver>(frontmatter by 字段)
    //   - badge/version-<ver>(README.md shield badge)
    // 其他位置的版本字串(如叙述句"v0.5.5 → v0.5.6 升级")不视为声明
    const isVersionDeclaration =
      /plugin[-_ ]version/i.test(line) ||
      /plugin 版本/i.test(line) ||
      /producer\/aeps-llm-wiki-plugin\/0\.\d+\.\d+/.test(line) ||
      /badge\/version-0\.\d+\.\d+/.test(line) ||
      /=.*'0\.\d+\.\d+'/.test(line);  // 常量赋值,如 PLUGIN_VERSION = '0.5.6'
    if (!isVersionDeclaration) continue;
    let m;
    VERSION_RE.lastIndex = 0;
    while ((m = VERSION_RE.exec(line)) !== null) {
      if (m[0] !== expectedVersion) {
        findings.push({
          file: absPath,
          line: i + 1,
          found: m[0],
          text: line.trim().slice(0, 120),
        });
      }
    }
  }
  return findings;
}

function main() {
  const expected = readPluginVersion();
  process.stderr.write(`[check-version] 期望版本:${expected}\n`);

  const targets = [];
  for (const root of SCAN_ROOTS) {
    const abs = path.join(PLUGIN_ROOT, root);
    if (!existsSync(abs)) continue;
    targets.push(...listFiles(abs));
  }
  for (const f of SCAN_FILES) {
    const abs = path.join(PLUGIN_ROOT, f);
    if (!existsSync(abs)) continue;
    const rel = f;
    if (shouldSkipByPath(rel)) continue;
    targets.push(abs);
  }

  const all = [];
  for (const f of targets) {
    all.push(...scanFile(f, expected));
  }

  if (all.length === 0) {
    process.stdout.write(`OK:全部 ${targets.length} 个文件的版本号字串均等于 ${expected}\n`);
    process.exit(0);
  }

  process.stdout.write(`FAIL:发现 ${all.length} 处版本号字串与 plugin.json(${expected})不一致:\n`);
  for (const f of all) {
    const rel = path.relative(PLUGIN_ROOT, f.file).replace(/\\/g, '/');
    process.stdout.write(`  ${rel}:${f.line}  ${f.found}  ← ${f.text}\n`);
  }
  process.exit(1);
}

try {
  main();
} catch (e) {
  process.stderr.write(`ERROR:${e.message}\n`);
  process.exit(2);
}
