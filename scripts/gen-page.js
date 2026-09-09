// gen-page.js — 按 page-{type}.md 模板 + 5 路径分流生成 wiki 页骨架
// PRD §4.1.1:确定性脚本生成 frontmatter + H2 顺序 + 维护说明尾巴;
// LLM 仅允许改 H2 之间的正文,不改字段值 / H2 顺序 / 维护说明尾巴.
//
// 用法:
//   node gen-page.js --type source --slug iso26262 \
//     --ext pdf --subdir 06_功能安全 \
//     [--project <用户工程绝对路径>] \
//     [--plugin-root <plugin 仓根绝对路径>] \
//     [--source-file '[[06-功能安全/iso26262.pdf|ISO 26262:2018 原文]]'] \
//     [--title 'ISO 26262:2018 功能安全标准']
//
// --project: 用户工程绝对路径;模板路径解析为 <project>/doc/templates/<name>(v0.5.8 起 doc/ 层级).
//           解析顺序:--project > env.WIKI_PROJECT(v0.5.8 起取消 cwd 兜底,AC-6).
// --plugin-root: plugin 仓绝对路径;读 .claude-plugin/plugin.json.
//               解析顺序:--plugin-root > env.CLAUDE_PLUGIN_ROOT > __dirname/../..
//
// type 取值: source / entity.{person,organization,project,product,event,place,other}
//           / concept.{theory,method,field,phenomenon,standard,term,other}
//           / analysis / comparison / synthesis
//
// exit: 0 OK / 1 参数错 / 2 模板缺失 / 3 写盘失败
//
// change history:
//   - 0.6.0: P0-#2 (issue #2) — 加 --patch-frontmatter-only flag:只 patch frontmatter 不动正文。
//     旧版 --out 重跑会覆盖 LLM 已填正文为占位符。新用法 SKILL.md 步骤 7。
//   - 0.6.4: P1-#7 — CLI --tags 真正生效:模板 tags: 后整段 list 被 args.tags(逗号 string 或 array)
//     替换;空 → 整段删除。
//     P1-#8 — --patch-frontmatter-only 合并前 strip undefined,避免 `{...existingFm, ...args}`
//     把 CLI 未传的 key 覆盖为 undefined 导致 resource / tags 等字段被清空。
//     P3-#10 — parseArgs boolean flag 判定显式三分支(undefined / `--` 起首 / 真值),
//     修复 --json / --apply / --patch-frontmatter-only 单传时 args[key] === undefined 的 bug。
//   - 0.6.5: WP-2 (issues #16/#17/#14) — frontmatter 注入管道统一重构:
//     ① 统一优先级「CLI 传入 > 脚本自动推导 > 模板默认」;--tags / --aliases /
//        --source-resource / --source-title 与 --description / --summary / --stale-after 同管道。
//     ② entity/concept 最小合规 skeleton:tags 按 DEFAULT_TAGS_BY_TYPE 注入(14 子类,
//        值取自 tag-spec.md 6 轴字典)、sources 对象格式 + 空时 stdout HINT、
//        stale_after 自动 generated.at + 1y(concept.standard +5y)、aliases fallback [title]、
//        description/summary fallback title。
//     ③ 彻底消灭 $ALIASES / $SOURCES 占位符:列表块替换泛化为 *_BODY 管道(TAGS/SOURCES/ALIASES),
//        page-source / page-entity / page-concept 三模板占位行删除、sources 改对象示例;
//        修复 CRLF 模板下块替换静默失效(--tags 被模板默认覆盖的 #16 真实根因)。
//     ④ --patch-frontmatter-only 复用同一管道 → 全 frontmatter 字段可 patch。

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { requireDeps } from "./lib/preflight.js";
// gen-page.js v0.6.0 (issue #2 fix): --patch-frontmatter-only 需要 js-yaml 读写已有 frontmatter
await requireDeps({ "js-yaml": "js-yaml" });
const yaml = (await import("js-yaml")).default;

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---- plugin 版本号 -------------------------------------------------------
// 从 plugin 本体 .claude-plugin/plugin.json 读取,而不是 scripts/package.json
// (scripts/package.json 是 scripts 私有包版本,与 plugin 本体版本解耦)
//
// 解析顺序(批次 1 修复 P0-3,design.md D1):
//   1. --plugin-root <absolute> CLI(最高优先级,SKILL.md 显式传)
//   2. process.env.CLAUDE_PLUGIN_ROOT(env,plugin loader 注入)
//   3. <import.meta.dirname>/../../.claude-plugin/plugin.json 探测
//      (脚本在 plugin 仓内被调用时命中,向后兼容老调用方式)
//   4. fallback 字符串 "unknown"(不是合法 semver,避免被误读为真实版本)
function resolvePluginRoot(cliArg) {
  if (cliArg) return resolve(cliArg);
  if (process.env.CLAUDE_PLUGIN_ROOT) return resolve(process.env.CLAUDE_PLUGIN_ROOT);
  const candidate = resolve(__dirname, "..", ".claude-plugin", "plugin.json");
  return existsSync(candidate) ? resolve(__dirname, "..") : null;
}

function readPluginVersion() {
  // 用 args 缓存:parseArgs 是模块内函数,这里通过 process.argv 重读一次;
  // 因为 readPluginVersion 在 renderFrontmatter 中调用,需要在 main 流程里 cache。
  const cli = (() => {
    const argv = process.argv.slice(2);
    const i = argv.indexOf("--plugin-root");
    return i >= 0 ? argv[i + 1] : null;
  })();
  const root = resolvePluginRoot(cli);
  if (!root) {
    console.error('WARN: plugin.json 读取失败,fallback "unknown"(未指定 --plugin-root,env CLAUDE_PLUGIN_ROOT 未注入,plugin 仓根探测失败)');
    return "unknown";
  }
  try {
    const pluginJsonPath = join(root, ".claude-plugin", "plugin.json");
    const txt = readFileSync(pluginJsonPath, "utf8");
    const json = JSON.parse(txt);
    return json.version || "unknown";
  } catch (e) {
    console.error(`WARN: plugin.json 读取失败(${root}/.claude-plugin/plugin.json),fallback "unknown": ${e.message}`);
    return "unknown";
  }
}

// ---- 5 路径分流 -----------------------------------------------------------
// 与 doc/template/page-source.md §4 路径分流表 + PRD §4.2 对齐.
// ext → { converter, native_text, converted_path 模板, 正文链接目标模板 }
const PATH_MAP = {
  // 路径 1:纯文本
  md:    { converter: "null",          native_text: true,  converted: null,                                linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}` },
  markdown:{ converter: "null",        native_text: true,  converted: null,                                linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}` },
  rst:   { converter: "null",          native_text: true,  converted: null,                                linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}` },
  txt:   { converter: "null",          native_text: true,  converted: null,                                linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}` },
  csv:   { converter: "null",          native_text: true,  converted: null,                                linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}` },
  json:  { converter: "null",          native_text: true,  converted: null,                                linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}` },
  yaml:  { converter: "null",          native_text: true,  converted: null,                                linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}` },
  yml:   { converter: "null",          native_text: true,  converted: null,                                linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}` },
  xml:   { converter: "null",          native_text: true,  converted: null,                                linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}` },
  // 路径 2:Claude 原生
  pdf:   { converter: "claude-native", native_text: true,  converted: null,                                linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}` },
  // 路径 3:第三方 / docling
  pptx:  { converter: "docling",       native_text: false, converted: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md`, linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md` },
  docx:  { converter: "docling",       native_text: false, converted: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md`, linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md` },
  xlsx:  { converter: "docling",       native_text: false, converted: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md`, linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md` },
  html:  { converter: "anydoc",        native_text: false, converted: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md`, linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md` },
  htm:   { converter: "anydoc",        native_text: false, converted: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md`, linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md` },
  // 路径 4:OCR
  png:   { converter: "paddleocr",     native_text: false, converted: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md`, linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md` },
  jpg:   { converter: "paddleocr",     native_text: false, converted: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md`, linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md` },
  jpeg:  { converter: "paddleocr",     native_text: false, converted: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md`, linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md` },
  bmp:   { converter: "paddleocr",     native_text: false, converted: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md`, linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md` },
  tiff:  { converter: "paddleocr",     native_text: false, converted: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md`, linkTarget: (b, s, e) => `./raw/${s}/${b}.${e}.converted.md` },
};

// type → 输出子目录(对齐 doc/template/README.md §2.4)
const TYPE_TO_DIR = {
  source: "sources",
  "entity.person": "entities/person",
  "entity.organization": "entities/organization",
  "entity.project": "entities/project",
  "entity.product": "entities/product",
  "entity.event": "entities/event",
  "entity.place": "entities/place",
  "entity.other": "entities/other",
  "concept.theory": "concepts/theory",
  "concept.method": "concepts/method",
  "concept.field": "concepts/field",
  "concept.phenomenon": "concepts/phenomenon",
  "concept.standard": "concepts/standard",
  "concept.term": "concepts/term",
  "concept.other": "concepts/other",
  analysis: "analyses",
  comparison: "comparisons",
  synthesis: "syntheses",
};

// ---- DEFAULT_TAGS_BY_TYPE(entity/concept 最小合规 tags skeleton)-----------------------
// v0.6.5 WP-2 (issues #14/#16):CLI 未传 --tags 时按 type 子类注入 ≥5 条最小 tags,
// 消灭「skeleton 全空值 → LLM 每页手工 Edit 6 字段」。取值规则:
//   - 每条值全部取自 doc/template/tag-spec.md 6 轴字典既有取值(冻结 v1.0)
//   - 含必填轴 docform/ + domain/(tag-spec §1.2),共 5 条(≥ schema minItems: 5)
//   - 不含人名 / 公司名 —— 实体身份由 aliases + 文件名承担(tag-spec §1.6.1)
//   - concept.standard 强绑定 maturity/standard、配 tec/iso26262(tag-spec §8 范式 1/3)
// LLM 在步骤 11 仍应按实际内容精修 tags,这里只保证 skeleton 一次 lint 即合规。
const DEFAULT_TAGS_BY_TYPE = {
  "entity.person":       ["docform/study-notes", "domain/ai", "layer/ai-agent", "tec/claude", "maturity/research"],
  "entity.organization": ["docform/whitepaper", "domain/ee-arch", "layer/chip", "maturity/production", "phase/ops"],
  "entity.project":      ["docform/technical-doc", "domain/process", "phase/requirements", "phase/verification", "maturity/pilot"],
  "entity.product":      ["docform/technical-doc", "domain/ee-arch", "layer/chip", "maturity/production", "phase/detail-design"],
  "entity.event":        ["docform/meeting-minutes", "domain/cross-domain", "layer/system", "maturity/concept", "phase/ops"],
  "entity.place":        ["docform/study-notes", "domain/geopolitics", "domain/cross-domain", "phase/ops", "maturity/concept"],
  "entity.other":        ["docform/study-notes", "domain/cross-domain", "layer/system", "maturity/concept", "phase/ops"],
  "concept.theory":      ["docform/article", "domain/ai", "layer/algorithm", "maturity/research", "phase/architecture"],
  "concept.method":      ["docform/technical-doc", "domain/process", "phase/architecture", "maturity/pilot", "layer/application"],
  "concept.field":       ["docform/article", "domain/cross-domain", "layer/system", "maturity/research", "phase/architecture"],
  "concept.phenomenon":  ["docform/article", "domain/cross-domain", "layer/algorithm", "phase/modeling", "maturity/research"],
  "concept.standard":    ["docform/standard-spec", "domain/fusa", "tec/iso26262", "layer/bsw-os", "maturity/standard"],
  "concept.term":        ["docform/study-notes", "domain/cross-domain", "layer/system", "phase/requirements", "maturity/concept"],
  "concept.other":       ["docform/study-notes", "domain/cross-domain", "layer/system", "phase/architecture", "maturity/concept"],
};

// ---- frontmatter 注入管道 helper(v0.6.5 WP-2)-----------------------------------------
// 统一优先级:CLI 传入 > 脚本自动推导 > 模板默认。

/** CLI list 入参归一:逗号分隔 string | array → string[](去空白、去空项);未传 → null */
function parseListArg(v) {
  if (v === undefined || v === null || v === "") return null;
  const arr = Array.isArray(v) ? v : String(v).split(",");
  const out = arr.map((s) => String(s).trim()).filter(Boolean);
  return out.length ? out : null;
}

/** ISO 8601 datetime + N 年 → "YYYY-MM-DDTHH:MM:SSZ"(entity/concept stale_after 自动推导) */
function addYearsIso(iso, years) {
  const d = new Date(iso);
  d.setUTCFullYear(d.getUTCFullYear() + years);
  return d.toISOString().replace(/\.\d{3}Z$/, "Z");
}

/** string[] → YAML list 块体(`  - x` 多行,无尾换行) */
function yamlListBody(items) {
  return items.map((t) => `  - ${t}`).join("\n");
}

/** 单个 sources 对象 → YAML object list 条目(合规格式,frontmatter-spec.md §4.4.1):
 *   - resource: "[[slug]]"
 *     title: "T"
 */
function yamlSourceObjBody(obj) {
  return Object.entries(obj)
    .map(([k, v], i) => `${i === 0 ? "  - " : "    "}${k}: ${JSON.stringify(v ?? "")}`)
    .join("\n");
}

/** sources 数组(元素可为对象或 legacy 字符串)→ YAML 块体;空数组 → "[]"(行内空数组) */
function renderSourcesBody(arr) {
  if (!arr.length) return "[]";
  return arr.map((item) => (item && typeof item === "object" ? yamlSourceObjBody(item) : `  - ${item}`)).join("\n");
}

/** 重写模板里 `key:` 的列表块(tags / sources / aliases)。
 *  replacement 语义:
 *   - undefined/null → 不动模板(保留模板默认 = 管道第三优先级)
 *   - ""             → 整块删除(含 key: 行与后续缩进行)
 *   - "[]"           → 行内空数组 `key: []`
 *   - 其余           → 块体 `key:\n<replacement>`(replacement 为 "  - x" 多行字符串)
 *  块边界:key: 行 + 其后所有缩进行(列表项与对象续行);遇空行 / 顶级字段 / `---` 止。
 *  注:`\n?` 兼容块位于 frontmatter 末尾(末行无换行符,fmBlock 不含收尾 `---`)的情形。
 */
function replaceListBlock(text, key, replacement) {
  if (replacement === undefined || replacement === null) return text;
  const re = new RegExp(`^${key}:[^\\n]*\\n(?:[ \\t]+[^\\n]*\\n?)*`, "gm");
  if (replacement === "") return text.replace(re, "");
  if (replacement === "[]") return text.replace(re, `${key}: []\n`);
  return text.replace(re, `${key}:\n${replacement}\n`);
}

// ---- 模板解析 ------------------------------------------------------------
// 提取 frontmatter 块原文(含注释行 / 字段顺序)+ H2 顺序;不动模板文件
// 兼容:模板顶部可能有 HTML 注释行(批次 1 模板骨架松绑后,L113-style 提示常用 `<!-- ... -->` 前缀)。
// 此处关心 frontmatter 块(原文)+ H2 顺序,不解析注释内容。
function parseTemplate(mdText) {
  // 跳过开头的注释行(<!-- ... -->)与空行,定位首个 --- 起始
  // v0.6.5 (issue #16 根因修复):模板文件在 Windows 检出常为 CRLF 行尾,而列表块替换
  // (TAGS_BODY / SOURCES_BODY / ALIASES_BODY)与 $KEY 空值删行都按 ^...$ 逐行匹配,
  // 行尾 \r 会让块匹配静默失败 → CLI --tags 被模板默认 tags 静默覆盖。fmBlock 统一归一为 LF。
  const cleaned = mdText.replace(/^(?:<!--[\s\S]*?-->\s*\r?\n)+/, '');
  const m = cleaned.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n([\s\S]*)$/);
  if (!m) throw new Error("template frontmatter parse failed");
  const fmBlock = m[1].replace(/\r\n/g, "\n"); // frontmatter 块原文(注释行 + 字段顺序保留,LF 归一)
  const fmNames = [...fmBlock.matchAll(/^([a-z_.]+):/gim)].map((x) => x[1]);
  const h2s = [...m[2].replace(/\r\n/g, "\n").matchAll(/^## (.+)$/gm)].map((x) => x[1].trim());
  return { fmBlock, fmNames, h2s };
}

// ---- frontmatter 占位符替换 ----------------------------------------------
// 模板 frontmatter 块里用 $KEY 标记派生字段;本函数按 placeholders 字典整体字符串替换。
// 设计原则:模板是字段名 / 字段顺序 / 注释行的**唯一事实源**,脚本只填值,不改顺序。
// 占位符语法:
//   - 列表块替换:tags / sources / aliases 走 *_BODY 管道(replaceListBlock),
//     模板里写**具体合规示例**(v0.6.5 起不再用 $SOURCES / $ALIASES 占位行),
//     脚本渲染时整体重写该块 → 输出永远无字面占位符,模板内容 = 脚本输出。
//   - 整行替换:key: $KEY        → key: <value>
//   - 行内替换:by: ".../$VER..." → by: ".../<version>..."(字符串里任意位置)
//
// ponytail:保留所有注释行(以 # 开头)和字段顺序;不调用 YAML 解析器,
// 直接字符串替换 —— YAML parser 会把 list / object 强转,破坏可读性。
//
// 空值处理:占位符为空时 → 整行删除(避免 `key: ` 这种 YAML 不合法残留)。
// v0.6.5:analysis / comparison / synthesis 模板(未纳入本次三模板改造)仍用
// `sources: $SOURCES` 行内占位符 → 走下方 $KEY 循环兼容;三新模板的块替换优先执行,
// 块替换后 $KEY 循环对已消失的占位符自然 no-op。
function renderFrontmatter(type, fmBlock, placeholders) {
  let out = fmBlock;

  // v0.6.5 WP-2:泛化列表块替换(TAGS_BODY / SOURCES_BODY / ALIASES_BODY)
  for (const [key, replacement] of Object.entries(placeholders)) {
    if (!key.endsWith("_BODY")) continue;
    out = replaceListBlock(out, key.replace(/_BODY$/, "").toLowerCase(), replacement);
  }

  for (const [key, value] of Object.entries(placeholders)) {
    if (key.endsWith("_BODY")) continue; // 已在上方块替换处理
    // 整 token 匹配:避免 $VER 误命中 $VERSION(前者不是占位符,后者是)
    const re = new RegExp(`\\$${key}\\b`, "g");
    if (value == null || value === "") {
      // 空值 → 整行删除
      // 两种形态:
      //   1. key: $KEY        → 删整行
      //   2. "$KEY"           → 行内,删占位符后整行变为空 → 删整行
      //   3. $SOURCES(多行占位符独占一行)→ 删整行
      out = out.replace(
        new RegExp(`^[^\\n]*\\$${key}\\b[^\\n]*\\n`, "gm"),
        ""
      );
    } else {
      out = out.replace(re, String(value));
    }
  }
  // 块替换后可能留下收尾空行(fmBlock 末尾无换行时补的 \n);统一收敛为一个换行
  return ["---", out.replace(/\n+$/, ""), "---"].join("\n");
}

// ---- 派生占位符字典 ------------------------------------------------------
// 把 PATH_MAP / 时间 / plugin 版本号 / args 折算成 placeholders 字典,
// 供 renderFrontmatter 按 $KEY / *_BODY 块替换。type 用于多类型分支。
//
// v0.6.5 WP-2 (issues #16/#17/#14) 统一注入管道,优先级:CLI 传入 > 脚本自动推导 > 模板默认:
//   - tags:--tags(逗号分隔 / array)> DEFAULT_TAGS_BY_TYPE(entity/concept)> 模板示例
//   - sources:--source-resource/--source-title(对象格式)> legacy --sources > [](空但合规 + HINT)
//   - aliases:--aliases(逗号分隔 / array)> [title] fallback(entity/concept/source)
//   - description / summary:CLI > title fallback(entity/concept)
//   - stale_after:--stale-after > generated.at + 1y(concept.standard +5y,对齐模板维护说明)
// 返回 { ph, hints }:hints 是给 LLM 的 stdout 提示(如 sources 为空需补 source)。
function derivePlaceholders(type, args) {
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const ext = (args.ext || "").toLowerCase().replace(/^\./, "");
  const map = PATH_MAP[ext] || null;
  const subdir = args.subdir || "";
  const isEntityConcept = type.startsWith("entity.") || type.startsWith("concept.");
  const title = args.title || args.slug;
  const hints = [];

  // ---- 标量字段 ----
  const ph = {
    NOW: now,
    VERSION: readPluginVersion(),
    TITLE: title,
    DESCRIPTION: args.description || (isEntityConcept ? title : ""),
    SUMMARY: args.summary || (isEntityConcept ? title : ""),
    STALE_AFTER: args.stale_after
      || (isEntityConcept ? addYearsIso(now, type === "concept.standard" ? 5 : 1) : ""),
  };

  // ---- tags:CLI --tags > DEFAULT_TAGS_BY_TYPE(entity/concept)> 模板默认(undefined → 不动模板)
  const cliTags = parseListArg(args.tags);
  if (cliTags) {
    ph.TAGS_BODY = yamlListBody(cliTags);
  } else if (isEntityConcept) {
    ph.TAGS_BODY = yamlListBody(DEFAULT_TAGS_BY_TYPE[type] || []);
  }

  // type 字段:source 直接填,entity.* / concept.* 保留 args.type 子类
  if (type === "source") {
    ph.TYPE = "source";
    ph.SLUG = args.slug;
    ph.EXT = ext || "md";
    ph.SUBDIR = subdir;
    ph.RESOURCE = args.resource
      || (ext ? `./raw/${subdir}/${args.slug}.${ext}` : "");
    // source_file:wikilink 形式 `[[{subdir}/{slug}.{ext}|{title}]]`,空 title 时省略 `|alias`
    const sFile = args.source_file
      || (ext ? `[[${subdir}/${args.slug}.${ext}${args.title ? `|${args.title}` : ""}]]` : "");
    ph.SOURCE_FILE = sFile;
    const converter = args.converter || (map ? map.converter : "null");
    const native = args.native_text !== undefined
      ? String(args.native_text)
      : (map ? String(map.native_text) : "true");
    const converted = args.converted_path !== undefined
      ? args.converted_path
      : (map && map.converted ? map.converted(args.slug, subdir, ext) : null);
    ph.CONVERTER = converter;
    ph.NATIVE_TEXT = native;
    ph.CONVERTED_PATH = converted == null ? "null" : `"${converted}"`;
    // v0.6.5:page-source.md 模板起带 aliases 字段;CLI > [title] fallback
    const srcAliases = parseListArg(args.aliases) || [title];
    ph.ALIASES_BODY = yamlListBody(srcAliases);
    ph.ALIASES = ph.ALIASES_BODY; // legacy $ALIASES 兜底(自定义旧模板)
  } else if (isEntityConcept) {
    // entity.* / concept.*:最小合规 skeleton(issue #14)
    ph.TYPE = args.type || type;

    // sources:对象格式 [{resource: "[[<source-slug>]]", title: "<source title>"}](issue #17)
    // 优先级:--source-resource/--source-title > legacy --sources > [](空但合规 + stdout HINT)
    const srcResource = typeof args.source_resource === "string" ? args.source_resource.trim() : "";
    const srcTitle = typeof args.source_title === "string" ? args.source_title.trim() : "";
    if (srcResource || srcTitle) {
      // 已带 [[..]] 的入参不重复包裹;只传其一 → 另一者用同一 slug 兜底
      const link = srcResource ? srcResource.replace(/^\[\[/, "").replace(/\]\]$/, "") : srcTitle;
      ph.SOURCES_BODY = renderSourcesBody([{ resource: `[[${link}]]`, title: srcTitle || link }]);
    } else if (Array.isArray(args.sources)) {
      // patch 模式:existingFm.sources YAML load 后的数组(对象 / legacy 字符串混排均可)
      ph.SOURCES_BODY = renderSourcesBody(args.sources);
    } else if (args.sources) {
      // legacy --sources 字符串列表(analysis 家族兼容写法;lint 对非对象格式会提示)
      ph.SOURCES_BODY = yamlListBody(String(args.sources).split(",").map((s) => s.trim()).filter(Boolean));
    } else {
      ph.SOURCES_BODY = "[]"; // 空但合规;main 向 stdout 提示 LLM 需补 source
      hints.push('sources 为空:LLM 需补 source(重跑 --patch-frontmatter-only --source-resource <source-slug> --source-title "<source title>")');
    }
    ph.SOURCES = ph.SOURCES_BODY === "[]" ? "" : ph.SOURCES_BODY; // legacy $SOURCES 兜底

    // aliases:CLI > [title] fallback(Obsidian 原生别名机制,frontmatter-spec §12.4)
    const cliAliases = parseListArg(args.aliases);
    ph.ALIASES_BODY = yamlListBody(cliAliases || [title]);
    ph.ALIASES = ph.ALIASES_BODY; // legacy $ALIASES 兜底
  } else {
    // analysis / comparison / synthesis:模板未纳入 v0.6.5 三模板改造,保持 legacy $SOURCES 行为
    ph.TYPE = args.type || type;
    if (Array.isArray(args.sources)) {
      ph.SOURCES = renderSourcesBody(args.sources);
    } else if (args.sources) {
      ph.SOURCES = yamlListBody(String(args.sources).split(",").map((s) => s.trim()).filter(Boolean));
    } else {
      ph.SOURCES = ""; // 模板里 sources: $SOURCES 整行被替换为空 → YAML 无 sources 字段
    }
  }

  // analysis / comparison / synthesis 必填 sources_count
  if (["analysis", "comparison", "synthesis"].includes(type)) {
    if (args.sources_count) {
      ph.SOURCES_COUNT = args.sources_count;
    } else if (args.sources_used) {
      ph.SOURCES_COUNT = String(args.sources_used.split(",").length);
    } else {
      ph.SOURCES_COUNT = "0";
    }
  }
  // analysis 专属必填
  if (type === "analysis") {
    ph.ANSWER_TO = args.answer_to || "";
    // sources_used:多行 YAML list 块
    if (args.sources_used) {
      const arr = parseListArg(args.sources_used) || [];
      ph.SOURCES_USED = yamlListBody(arr);
    } else {
      ph.SOURCES_USED = "";
    }
  }
  return { ph, hints };
}

// ---- 渲染正文骨架 --------------------------------------------------------
function renderBody(type, tpl, args) {
  const lines = [];
  // 占位 H1 = title 或 slug
  lines.push(`# ${args.title || args.slug}`);
  lines.push("");

  const ext = (args.ext || "").toLowerCase().replace(/^\./, "");
  const map = PATH_MAP[ext] || null;

  // 维护说明类 H2:模板里自带的文档段,脚本不填占位、不再追加尾巴
  const isMaintain = (h) => h.includes("维护说明") || h.includes("字段一致性 lint");

  for (const h2 of tpl.h2s) {
    lines.push(`## ${h2}`);
    lines.push("");
    if (isMaintain(h2)) {
      // 跳过,占位由 SKILL.md 直接读模板原文
      continue;
    }
    if (type === "source" && h2 === "重点摘录" && map) {
      const target = map.linkTarget(args.slug, args.subdir || "", ext);
      lines.push(`> 原始来源:[${args.slug}](${target})`);
      lines.push("");
      lines.push("【LLM 自动填充:从原文摘录 3-5 条要点】");
    } else if (h2 === "我的思考") {
      lines.push("【LLM 自动填充:研究问题、与其他 wiki 页的联系、可深挖方向】");
    } else if (h2 === "总结:最有收获的一句话") {
      lines.push("【LLM 自动填充:一句话 core verdict,≤ 50 字】");
    } else if (type === "source" && h2 === "阅读路线") {
      // v0.5.9:阅读路线占位骨架,LLM 必须改造(改节名 / 拆多节 / 短文豁免一句话说明)
      lines.push("【v0.5.9 占位骨架,LLM 必改:读完源文件后,先问『这篇有什么独特结构』,再用 1-N 个 H2 节呈现;强烈建议改名(如 ## 来源元信息 / ## 核心要点 / ## 关键引用 / ## 适用范围 / ## 术语定义 / ## 关键约束 / ## 技术原理 / ## 性能指标 / ## 与同类对比 / ## 研究背景 / ## 方法 / ## 结果 / ## 结论 等);极短源文件可保留此名 + 一句豁免说明。所有内容强制溯源,无法溯源标 [来源不足,需人工复核]】");
    } else if (type === "analysis" && h2 === "方案推演 / 架构分析") {
      lines.push("【LLM 综合推演正文。从 query 引用的 wiki 页中抽取关键事实,组织成有逻辑链的方案推演】");
    } else if (type === "analysis" && h2 === "关联溯源") {
      lines.push("【本次推演用到的关键 Wiki 事实与依据】");
      lines.push("");
      if (args.sources_used) {
        const links = args.sources_used.split(",").map((s) => `[[${s.trim().replace(/^\.\/knowledge\//, "").replace(/\.md$/, "")}]]`).join(", ");
        lines.push(`> 引用:${links}`);
      }
    } else if (h2.startsWith("相关页面")) {
      lines.push("【本节由 /aeps-llm-wiki-ingest 自动生成,LLM 不修改】");
      lines.push("");
      lines.push("### Entities");
      lines.push("");
      lines.push("【自动填充相关实体页链接;无相关实体时省略本小节】");
      lines.push("");
      lines.push("### Concepts");
      lines.push("");
      lines.push("【自动填充相关概念页链接;无相关概念时省略本小节】");
    } else {
      lines.push(`【LLM 自动填充:${h2}】`);
    }
    lines.push("");
  }

  // 注意:维护说明尾巴由模板自带(每个 page-*.md 都有 ## 维护说明 H2),
  // 上面 isMaintain 已跳过占位填充 —— 不再额外追加,避免重复 H2.

  return lines.join("\n");
}

// ---- 主流程 --------------------------------------------------------------
// v0.6.4 (issue #10 fix): 修正 boolean flag(无值)的判定 ——
//   旧实现 `out[key] = v && !v.startsWith("--") ? v : true` 在 `v = undefined` 时
//   `v && ...` 短路成 undefined,导致 `--json` 单传时 args.json === undefined
//   (而非 true),后续 `if (args.json)` 全部失效,并在并发场景下让 parseArgs
//   行为不可预测。新实现显式三分支:有值 → 用值;无值 → true;没 -- 前缀 → true。
function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (!k.startsWith("--")) continue;
    const key = k.slice(2).replace(/-/g, "_");
    const v = argv[i + 1];
    if (v === undefined || v.startsWith("--")) {
      // boolean flag(--json / --apply / --patch-frontmatter-only 等)
      out[key] = true;
    } else {
      out[key] = v;
      i++;
    }
  }
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.type || !args.slug) {
    console.error("ERROR: --type 和 --slug 必填");
    process.exit(1);
  }
  const type = args.type;
  if (!TYPE_TO_DIR[type]) {
    console.error(`ERROR: unknown type: ${type}`);
    process.exit(1);
  }

  // analysis / comparison / synthesis 必填字段验证(对齐 doc/template/page-{analysis,comparison,synthesis}.md)
  // 防止静默生成残缺 frontmatter,触发下游 build-related-pages ajv 校验失败。
  if (type === "analysis" && !args.answer_to) {
    console.error("ERROR: --type analysis 必须 --answer-to (query 问题原文,30-80 字)");
    process.exit(1);
  }
  if (["analysis", "comparison", "synthesis"].includes(type) && !args.sources_used && !args.sources_count) {
    console.error(`ERROR: --type ${type} 必须 --sources-used 或 --sources-count`);
    process.exit(1);
  }

  // 模板文件:无 frontmatter 特殊页(no-frontmatter)直接拼空 frontmatter
  // v0.5.7 起:entity.* / concept.* 7 子类统一走 page-entity.md / page-concept.md 通用模板,
  // 旧的 14 个差异化模板(page-entity-{person,...}.md / page-concept-{theory,...}.md)已删除.
  const tplName = (() => {
    if (type === "source") return "page-source.md";
    if (type.startsWith("entity.")) return "page-entity.md";
    if (type.startsWith("concept.")) return "page-concept.md";
    return `page-${type}.md`;
  })();

  // 用户工程根解析(对齐 design.md D2,批次 2 修复 P1-2,v0.5.8 起 templates/ → doc/templates/):
  //   1. --project <absolute>(SKILL.md 显式传,最高优先级)
  //   2. process.env.WIKI_PROJECT(env)
  //   3. 否则回退 plugin doc/template/<name>(plugin 自检路径,向后兼容老调用方式)
  // ponytail: v0.5.8 起取消 cwd 兜底(cwd 不可靠;AC-6)。显式 --project 必须从 <project>/doc/templates/ 找。
  const projectRoot = (() => {
    if (args.project) return resolve(String(args.project));
    if (process.env.WIKI_PROJECT) return resolve(process.env.WIKI_PROJECT);
    return null;
  })();

  // 模板搜索路径:
  //   - 若显式 --project → 严格从 <project>/doc/templates/<name> 找(v0.5.8 起 doc/ 子目录)
  //     找不到 → ERROR,提示用户 sync templates 或检查路径。
  //   - 否则(无 --project)→ 优先 projectRoot/doc/templates/,fallback plugin doc/template/(向后兼容老调用)
  const candidates = [];
  if (args.project || process.env.WIKI_PROJECT) {
    // 显式 --project / WIKI_PROJECT → 严格模式
    candidates.push(resolve(projectRoot, "doc", "templates", tplName));
  } else {
    if (projectRoot) candidates.push(resolve(projectRoot, "doc", "templates", tplName));
    candidates.push(resolve(__dirname, "..", "doc", "template", tplName));
  }
  const tplPath = candidates.find((p) => existsSync(p));
  if (!tplPath) {
    console.error(`ERROR: template not found: ${tplName} (looked in ${candidates.join(", ")}). Pass --project <absolute> to specify user project root.`);
    process.exit(2);
  }
  const tplText = readFileSync(tplPath, "utf8");
  const tpl = parseTemplate(tplText);

  // v0.6.1:frontmatter 由模板 fmBlock 原文 + 占位符替换生成(模板是字段顺序 / 注释的唯一事实源)
  const { ph, hints } = derivePlaceholders(type, args);
  const fm = renderFrontmatter(type, tpl.fmBlock, ph);
  const body = renderBody(type, tpl, args);
  const out = fm + "\n" + body;

  // 输出路径:knowledge/{TYPE_TO_DIR}/{slug}.md 或 --out 指定
  // 用户工程根用上面解析的 projectRoot,与 templates 路径同源
  const outPath = args.out
    ? resolve(args.out)
    : resolve(projectRoot, "knowledge", TYPE_TO_DIR[type], `${args.slug}.md`);
  mkdirSync(dirname(outPath), { recursive: true });

  // v0.6.0 (issue #2 fix): --patch-frontmatter-only 模式:只 patch frontmatter,不动正文
  // v0.6.4 (issue #8 fix): mergedArgs spread 前必须 strip undefined —— 否则
  //   `{...existingFm, ...args}` 会把 `args.tags === undefined` 这种「CLI 未传」
  //   字段覆盖到 existingFm.tags 上,导致 derivePlaceholders 看到 undefined →
  //   空值 → 整行删 → **resource / tags / sources 等未传字段被清空**。
  //   现在只把 args 里**实际有值**(非 undefined)的 key 覆盖过去,「CLI 未传」让位给 existingFm。
  if (args.patch_frontmatter_only) {
    if (!existsSync(outPath)) {
      console.error(`WARN: --patch-frontmatter-only 目标文件不存在: ${outPath};fallback 全量生成`);
    } else {
      const existing = readFileSync(outPath, "utf8");
      const m = existing.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
      if (!m) {
        console.error(`ERROR: --patch-frontmatter-only 目标文件无 frontmatter: ${outPath}`);
        process.exit(3);
      }
      let existingFm = {};
      try { existingFm = yaml.load(m[1]) || {}; } catch (e) {
        console.error(`ERROR: 解析现有 frontmatter 失败: ${e.message}`);
        process.exit(3);
      }
      // 过滤 undefined:CLI 没传的 key 不应该覆盖 existingFm 的值
      const definedArgs = {};
      for (const [k, v] of Object.entries(args)) {
        if (v !== undefined) definedArgs[k] = v;
      }
      // 归一 list 字段:CLI 传逗号分隔 string ↔ YAML load 后 array ↔ derivePlaceholders 内部已支持两种
      // 但 alias 字段若 existingFm 是 array 而 CLI 没传,mergedArgs.aliases 应保留 array(已 OK)
      const mergedArgs = { ...existingFm, ...definedArgs };
      const { ph: newPh, hints: newHints } = derivePlaceholders(type, mergedArgs);
      const newFm = renderFrontmatter(type, tpl.fmBlock, newPh);
      const existingBody = m[2];
      const patched = newFm + "\n" + existingBody;
      try {
        writeFileSync(outPath, patched, "utf8");
      } catch (e) {
        console.error(`ERROR: write failed: ${outPath}: ${e.message}`);
        process.exit(3);
      }
      console.log(`OK: ${type} → ${outPath} (patched frontmatter only, ${patched.length} bytes)`);
      for (const h of newHints) console.log(`HINT: ${h}`);
      return;
    }
  }

  try {
    writeFileSync(outPath, out, "utf8");
  } catch (e) {
    console.error(`ERROR: write failed: ${outPath}: ${e.message}`);
    process.exit(3);
  }
  console.log(`OK: ${type} → ${outPath} (${out.length} bytes)`);
  for (const h of hints) console.log(`HINT: ${h}`);
}

main();