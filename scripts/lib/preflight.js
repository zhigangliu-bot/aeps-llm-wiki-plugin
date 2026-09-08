#!/usr/bin/env node
/**
 * preflight.js — scripts/lib/preflight.js(可复用 inline preflight)
 *
 * 用途:
 *   每个脚本入口 inline 调用 `await requireDeps({ yaml: 'js-yaml', ajv: 'ajv' })`,
 *   缺包时立即 throw Error(由调用方决定 exit code),错误信息含精确 `npm install <pkg>` 命令。
 *   与 scripts/ingest/preflight.js(SKILL.md 步骤 0.5 主动调用)并存不冲突。
 *
 * API:
 *   await requireDeps({ <importName>: <npmPackageName>, ... })
 *     - importName:  package 名(Node.js 解析时用)
 *     - npmPackageName: npm install 的包名(可能与 importName 不同)
 *
 * 退出语义:
 *   缺包 → throw Error(消息含 npm install 命令);调用方用 try/catch 或顶层 .catch 处理 exit code
 *   齐备 → silent return,继续执行后续业务逻辑
 *
 * 实现:
 *   - 用 createRequire 检测包是否能 require.resolve 找到
 *   - 静态 import 失败 → 由调用方决定;requireDeps 只做"已能 resolve 的包列表"校验
 *
 * 用法示例(每个 ingest/init 脚本顶部):
 *   import { requireDeps } from '../lib/preflight.js';
 *   await requireDeps({ 'js-yaml': 'js-yaml', ajv: 'ajv' });
 */

import { createRequire } from 'node:module';
import process from 'node:process';

const _req = createRequire(import.meta.url);

/**
 * 检查 modules 字典里的所有 npm 包是否可解析;缺包 → throw 含精确修复命令
 *
 * @param {Record<string, string>} modules - { importName: npmPkgName } 映射
 * @throws {Error} 缺依赖时抛错,msg 含 `npm install <pkg>` 命令
 */
export async function requireDeps(modules) {
  const missing = [];
  for (const [importName, pkgName] of Object.entries(modules)) {
    try {
      // 用 require.resolve 检测包路径(不会实际加载,只解析路径)
      _req.resolve(importName);
    } catch {
      missing.push({ importName, pkg: pkgName });
    }
  }

  if (missing.length > 0) {
    const cmds = missing.map((m) => `npm install ${m.pkg}`).join('\n  ');
    const pkgList = missing.map((m) => m.pkg).join(', ');
    const msg = `缺依赖 ${missing.length} 个: ${pkgList}\nHINT: 在 plugin 仓 scripts/ 目录下执行:\n  ${cmds}`;
    const err = new Error(msg);
    err.code = 'AEPS_MISSING_DEPS';
    err.missing = missing;
    throw err;
  }
}
