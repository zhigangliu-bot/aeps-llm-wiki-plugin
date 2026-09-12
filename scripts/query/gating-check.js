#!/usr/bin/env node
/**
 * gating-check.js — query 步骤 8:G11 gating 判定(4×4 矩阵机械部分)
 *
 * Usage:
 *   node scripts/query/gating-check.js \
 *     --intent <overview|comparison|exact|ambiguous|other> \
 *     --answer-words <n> --hit-pages "<path1,path2,...>" [--not-covered] --json
 *
 * 判定(implement-query.md §1.1 冻结判定表,全 trigger 任一命中 且 全 skip 均不命中
 * → should_ask: true;skip 优先于 trigger):
 *
 *   triggers(任一命中)              skips(任一命中即跳过)
 *   ------------------------------  ------------------------------
 *   intent=overview                 intent=exact
 *   intent=comparison               intent=ambiguous
 *   hit_dirs>=2(首段去重计数)      answer_words<200
 *   answer_words>=200               hit_pages<2
 *                                   not_covered=true
 *
 * 边界:
 *   - intent 由 LLM 传入(步骤 1 语义判定);机械量(字数比较 / 命中页数 /
 *     子目录去重)由本脚本算 —— LLM 不做算术,防 gating 误判
 *   - hit_dirs:hit-pages 每条按 knowledge/<dir>/ **首段**去重计数
 *     (`entities/person/a.md` 与 `entities/product/b.md` 首段同为 `entities` → 1)
 *   - --answer-words 字数口径由调用方按「空白分词 + CJK 逐字计数」口径预先算好传入
 *     (implement-query.md §4 风险表;边界 ±1 字不影响拍板门)
 *   - ambiguous fallthrough 永不落档;路径 C 触发词(vs/对比/区别/异同/优缺点)
 *     只是 LLM 推断 intent 的辅助,不改变 fallthrough(PRD §4.3 Intent 路由)
 *
 * JSON stdout 契约:
 *   { "should_ask": true, "triggers": ["intent=overview"], "skips": [] }
 *   exit 0 成功 / 1 用法错误(非法 intent / 非法字数 / 缺必填参数)
 */

import process from 'node:process';

const VALID_INTENTS = ['overview', 'comparison', 'exact', 'ambiguous', 'other'];
// 冻结字数阈值(PRD §4.3 gating 表:回答字数 ≥ 200 触发 / < 200 不触发)
const ANSWER_WORDS_TRIGGER = 200;

function parseArgs(argv) {
  const args = { intent: null, answerWords: null, hitPages: [], notCovered: false, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--intent') args.intent = argv[++i];
    else if (a === '--answer-words') args.answerWords = argv[++i];
    else if (a === '--hit-pages') args.hitPagesRaw = argv[++i];
    else if (a === '--not-covered') args.notCovered = true;
    else if (a === '--json') args.json = true;
  }
  return args;
}

function usageError(msg) {
  console.error(`ERROR: ${msg}`);
  console.error('Usage: node gating-check.js --intent <overview|comparison|exact|ambiguous|other> --answer-words <n> --hit-pages "<p1,p2,...>" [--not-covered] --json');
  process.exit(1);
}

/**
 * hit-pages 按 knowledge/<dir>/ 首段去重计数。
 * 归一:反斜杠 → 正斜杠;剥前导 ./ 与 knowledge/;取第一个路径段;
 * 根级文件(无目录段)计为 "."(根)。
 */
function countHitDirs(rawPages) {
  const dirs = new Set();
  for (const p of rawPages) {
    let s = String(p).trim().replace(/\\/g, '/');
    while (s.startsWith('./')) s = s.slice(2);
    if (s.startsWith('knowledge/')) s = s.slice('knowledge/'.length);
    if (!s) continue;
    const first = s.includes('/') ? s.slice(0, s.indexOf('/')) : '.';
    dirs.add(first);
  }
  return dirs.size;
}

function main() {
  const args = parseArgs(process.argv.slice(2));

  if (!args.intent) usageError('--intent 必填');
  if (!VALID_INTENTS.includes(args.intent)) {
    usageError(`--intent 非法: ${args.intent}(合法值: ${VALID_INTENTS.join(' | ')})`);
  }
  const wordsRaw = args.answerWords;
  if (wordsRaw === null || wordsRaw === undefined || wordsRaw === '' || !/^\d+$/.test(String(wordsRaw))) {
    usageError(`--answer-words 必须是非负整数,收到: ${wordsRaw}`);
  }
  const answerWords = Number(wordsRaw);

  const hitPages = String(args.hitPagesRaw || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const hitDirs = countHitDirs(hitPages);

  // ---- triggers(任一命中)----
  const triggers = [];
  if (args.intent === 'overview') triggers.push('intent=overview');
  if (args.intent === 'comparison') triggers.push('intent=comparison');
  if (hitDirs >= 2) triggers.push('hit_dirs>=2');
  if (answerWords >= ANSWER_WORDS_TRIGGER) triggers.push(`answer_words>=${ANSWER_WORDS_TRIGGER}`);

  // ---- skips(任一命中即跳过;skip 优先于 trigger)----
  const skips = [];
  if (args.intent === 'exact') skips.push('intent=exact');
  if (args.intent === 'ambiguous') skips.push('intent=ambiguous');
  if (answerWords < ANSWER_WORDS_TRIGGER) skips.push(`answer_words<${ANSWER_WORDS_TRIGGER}`);
  if (hitPages.length < 2) skips.push('hit_pages<2');
  if (args.notCovered) skips.push('not_covered=true');

  const shouldAsk = triggers.length > 0 && skips.length === 0;

  // 诊断到 stderr:hit_dirs 计算是脚本内部机械推导,打印出来便于 SKILL.md 展示核对
  console.error(`[gating] intent=${args.intent} answer_words=${answerWords} hit_pages=${hitPages.length} hit_dirs=${hitDirs} → should_ask=${shouldAsk}`);

  console.log(JSON.stringify({ should_ask: shouldAsk, triggers, skips }, null, 2));
  process.exit(0);
}

main();
