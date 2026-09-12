#!/usr/bin/env node
/**
 * count-pages.js — query 步骤 0:wiki 规模探查 → 引擎分流
 *
 * Usage:
 *   node scripts/query/count-pages.js --project <用户工程根> --json
 *
 * 行为:
 *   - 递归数 <project>/knowledge/ 下全部 .md 文件(递归 glob `**`;含 reserved
 *     index/overview/glossary/log 四文件,与 PRD §4.3 字面一致,不做剔除特判)
 *   - 按页数给出 scale / engine / qmd_required(design §7.6 唯一阈值升级条款):
 *       pages <  QUERY_INDEX_THRESHOLD(500)       → small  / index      / false
 *       500 ≤ pages ≤ QUERY_QMD_REQUIRED_THRESHOLD → medium / prefer-qmd / false
 *       pages > QUERY_QMD_REQUIRED_THRESHOLD(1000) → large  / require-qmd / true
 *   - knowledge/ 目录不存在 → ERROR exit 1(先跑 init)
 *
 * JSON stdout 契约(implement-query.md §1.1):
 *   { "pages": 123, "scale": "small", "engine": "index", "qmd_required": false }
 *   诊断 / 进度到 stderr;exit 0 成功 / 1 用法或环境错误
 *
 * 边界:
 *   - 0 新 npm 依赖(纯 node:fs / node:path)
 *   - 用户工程根一律 --project 传入,代码中无绝对路径
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

// 阈值常量(design.md §7.6 冻结值,不得调整)
export const QUERY_INDEX_THRESHOLD = 500;
export const QUERY_QMD_REQUIRED_THRESHOLD = 1000;

function parseArgs(argv) {
  const args = { project: null, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--json') args.json = true;
  }
  if (!args.project) {
    console.error('ERROR: --project <用户工程根> 必填');
    process.exit(1);
  }
  return args;
}

/** 递归收集 dir 下全部 .md 文件路径(跟随目录,不跟符号链接语义从简) */
async function listMarkdownFiles(dir) {
  const out = [];
  let entries;
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch (e) {
    // ENOENT:目录不存在;ENOTDIR:knowledge/ 路径段是普通文件 —— 契约同义"目录不存在" → exit 1
    if (e.code === 'ENOENT' || e.code === 'ENOTDIR') return null;
    throw e;
  }
  for (const ent of entries) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      const sub = await listMarkdownFiles(full);
      if (sub) out.push(...sub);
    } else if (ent.isFile() && ent.name.toLowerCase().endsWith('.md')) {
      out.push(full);
    }
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const project = path.resolve(args.project);
  const knowledgeDir = path.join(project, 'knowledge');

  const files = await listMarkdownFiles(knowledgeDir);
  if (files === null) {
    console.error(`ERROR: knowledge/ 目录不存在: ${knowledgeDir}(先跑 /aeps-llm-wiki-init 初始化 vault)`);
    process.exit(1);
  }

  const pages = files.length;
  let scale;
  let engine;
  let qmdRequired;
  if (pages < QUERY_INDEX_THRESHOLD) {
    scale = 'small';
    engine = 'index';
    qmdRequired = false;
  } else if (pages <= QUERY_QMD_REQUIRED_THRESHOLD) {
    scale = 'medium';
    engine = 'prefer-qmd';
    qmdRequired = false;
  } else {
    scale = 'large';
    engine = 'require-qmd';
    qmdRequired = true;
  }

  // 诊断到 stderr(stdout 只留 JSON,SKILL.md 直接 JSON.parse)
  console.error(`[count-pages] knowledge/**/*.md = ${pages} → scale=${scale} engine=${engine} qmd_required=${qmdRequired}`);

  if (args.json) {
    console.log(JSON.stringify({ pages, scale, engine, qmd_required: qmdRequired }, null, 2));
  } else {
    console.log(`pages=${pages} scale=${scale} engine=${engine} qmd_required=${qmdRequired}`);
  }
  process.exit(0);
}

main().catch((err) => {
  console.error(`ERROR: ${err.message}`);
  process.exit(2);
});
