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

// ---- 模板解析 ------------------------------------------------------------
// 提取 frontmatter 块原文(含注释行 / 字段顺序)+ H2 顺序;不动模板文件
// 兼容:模板顶部可能有 HTML 注释行(批次 1 模板骨架松绑后,L113-style 提示常用 `<!-- ... -->` 前缀)。
// 此处关心 frontmatter 块(原文)+ H2 顺序,不解析注释内容。
function parseTemplate(mdText) {
  // 跳过开头的注释行(<!-- ... -->)与空行,定位首个 --- 起始
  const cleaned = mdText.replace(/^(?:<!--[\s\S]*?-->\s*\n)+/, '');
  const m = cleaned.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  if (!m) throw new Error("template frontmatter parse failed");
  const fmBlock = m[1];          // frontmatter 块原文(注释行 + 字段顺序保留)
  const fmNames = [...fmBlock.matchAll(/^([a-z_.]+):/gim)].map((x) => x[1]);
  const h2s = [...m[2].matchAll(/^## (.+)$/gm)].map((x) => x[1].trim());
  return { fmBlock, fmNames, h2s };
}

// ---- frontmatter 占位符替换 ----------------------------------------------
// 模板 frontmatter 块里用 $KEY 标记派生字段;本函数按 placeholders 字典整体字符串替换。
// 设计原则:模板是字段名 / 字段顺序 / 注释行的**唯一事实源**,脚本只填值,不改顺序。
// 占位符语法:
//   - 整行替换:key: $KEY        → key: <value>
//   - 行内替换:by: ".../$VER..." → by: ".../<version>..."(字符串里任意位置)
//   - 多行替换:$SOURCES / $SOURCES_USED / $ALIASES 整体替换为对应 YAML 块
//
// ponytail:保留所有注释行(以 # 开头)和字段顺序;不调用 YAML 解析器,
// 直接字符串替换 —— YAML parser 会把 list / object 强转,破坏可读性。
//
// 空值处理:占位符为空时 → 整行删除(避免 `key: ` 这种 YAML 不合法残留)。
// 多行占位符($SOURCES / $SOURCES_USED / $ALIASES)空值时同样整行删。
function renderFrontmatter(type, fmBlock, placeholders) {
  let out = fmBlock;
  // 多行占位符白名单:这些占位符可能占据 `key: $KEY` 整行,且替换后是多行 YAML list
  const multiLineKeys = new Set(["SOURCES", "SOURCES_USED", "ALIASES"]);

  for (const [key, value] of Object.entries(placeholders)) {
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
      // 替换后,如果该行是 `key: <多行值>`(value 含换行),保持原状;
      // 如果是 `key: <单行值>` 也保持原状。
      // 但需要修正:多行占位符(如 $SOURCES)被替换为多行 YAML list,
      // 模板里是 `sources: $SOURCES` 单行 → 替换后变成 `sources: \n  - foo\n  - bar`,
      // YAML 合法(list 作为 block scalar),保持。
    }
  }
  return ["---", out, "---"].join("\n");
}

// ---- 派生占位符字典 ------------------------------------------------------
// 把 PATH_MAP / 时间 / plugin 版本号 / args 折算成 placeholders 字典,
// 供 renderFrontmatter 按 $KEY 替换。type 用于多类型分支(analysis / source 等)。
function derivePlaceholders(type, args) {
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const ext = (args.ext || "").toLowerCase().replace(/^\./, "");
  const map = PATH_MAP[ext] || null;
  const subdir = args.subdir || "";

  const ph = {
    NOW: now,
    VERSION: readPluginVersion(),
    TITLE: args.title || args.slug,
    DESCRIPTION: args.description || "",
    SUMMARY: args.summary || "",
    STALE_AFTER: args.stale_after || "",
  };

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
  } else {
    // entity.* / concept.* / analysis / comparison / synthesis
    ph.TYPE = args.type || type;
    // sources:多行 YAML list 块
    if (args.sources) {
      // 用户显式传 → 直接用(支持字符串或数组)
      const arr = Array.isArray(args.sources) ? args.sources : String(args.sources).split(",").map((s) => s.trim());
      ph.SOURCES = arr.map((s) => `  - ${s}`).join("\n");
    } else {
      ph.SOURCES = "";   // 模板里 sources: $SOURCES 整行被替换为空 → YAML 无 sources 字段
    }
    if (Array.isArray(args.aliases) && args.aliases.length > 0) {
      ph.ALIASES = args.aliases.map((a) => `  - ${JSON.stringify(a)}`).join("\n");
    } else if (typeof args.aliases === "string" && args.aliases.trim()) {
      ph.ALIASES = args.aliases.split(",").map((a) => `  - ${JSON.stringify(a.trim())}`).join("\n");
    } else {
      ph.ALIASES = "";
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
      const arr = args.sources_used.split(",").map((s) => s.trim());
      ph.SOURCES_USED = arr.map((s) => `  - ${s}`).join("\n");
    } else {
      ph.SOURCES_USED = "";
    }
  }
  return ph;
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
function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (!k.startsWith("--")) continue;
    const key = k.slice(2).replace(/-/g, "_");
    const v = argv[i + 1];
    out[key] = v && !v.startsWith("--") ? v : true;
    if (v && !v.startsWith("--")) i++;
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
  const placeholders = derivePlaceholders(type, args);
  const fm = renderFrontmatter(type, tpl.fmBlock, placeholders);
  const body = renderBody(type, tpl, args);
  const out = fm + "\n" + body;

  // 输出路径:knowledge/{TYPE_TO_DIR}/{slug}.md 或 --out 指定
  // 用户工程根用上面解析的 projectRoot,与 templates 路径同源
  const outPath = args.out
    ? resolve(args.out)
    : resolve(projectRoot, "knowledge", TYPE_TO_DIR[type], `${args.slug}.md`);
  mkdirSync(dirname(outPath), { recursive: true });

  // v0.6.0 (issue #2 fix): --patch-frontmatter-only 模式:只 patch frontmatter,不动正文
  // 用法:`gen-page.js --out foo.md --patch-frontmatter-only --summary "..." --title "..."`
  //   - 目标文件存在 → 解析现有 YAML,合并传入字段(只覆盖传入的 key),正文保持不变
  //   - 目标文件不存在 → fallback 全量生成(打印 WARN)
  //   - 不传 --patch-frontmatter-only → 行为不变(全量写,SKILL.md 步骤 6 用)
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
      // 把现有 frontmatter 当成 args 来源 + 新 args 覆盖;再 derivePlaceholders 一次得到完整新 fm
      // normalize: tags / sources_used / aliases 等可能 array(YAML 解析)也可能 string(CLI 传)
      const mergedArgs = { ...existingFm, ...args };
      // YAML load 已经把 list 转 array,CLI 传 string — derivePlaceholders 已统一处理
      const newPh = derivePlaceholders(type, mergedArgs);
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
}

main();