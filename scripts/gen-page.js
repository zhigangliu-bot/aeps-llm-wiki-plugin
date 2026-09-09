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

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { requireDeps } from "./lib/preflight.js";
// gen-page.js 不依赖 npm 包(纯 node:fs);inline preflight 用空对象探活
await requireDeps({});

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
// 仅提取 frontmatter 字段名骨架 + H2 顺序;不动模板文件
// 兼容:模板顶部可能有 HTML 注释行(批次 1 模板骨架松绑后,L113-style 提示常用 `<!-- ... -->` 前缀)。
// 此处只关心 frontmatter 块 + H2 顺序,不解析注释内容。
function parseTemplate(mdText) {
  // 跳过开头的注释行(<!-- ... -->)与空行,定位首个 --- 起始
  const cleaned = mdText.replace(/^(?:<!--[\s\S]*?-->\s*\n)+/, '');
  const m = cleaned.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/);
  if (!m) throw new Error("template frontmatter parse failed");
  const fmNames = [...m[1].matchAll(/^([a-z_]+):/gm)].map((x) => x[1]);
  const h2s = [...m[2].matchAll(/^## (.+)$/gm)].map((x) => x[1].trim());
  return { fmNames, h2s };
}

// ---- 渲染 frontmatter ----------------------------------------------------
function renderFrontmatter(type, args) {
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const ext = (args.ext || "").toLowerCase().replace(/^\./, "");
  const map = PATH_MAP[ext] || null;
  const converter = args.converter || (map ? map.converter : "null");
  const native = args.native_text !== undefined
    ? String(args.native_text)
    : (map ? String(map.native_text) : "true");
  const converted = args.converted_path !== undefined
    ? args.converted_path
    : (map && map.converted ? map.converted(args.slug, args.subdir || "", ext) : "null");

  const lines = [];
  lines.push("---");
  lines.push(`type: ${type}`);
  if (args.title) lines.push(`title: "${args.title}"`);
  if (args.description) lines.push(`description: "${args.description}"`);
  if (args.tags) {
    lines.push("tags:");
    for (const t of args.tags.split(",")) lines.push(`  - ${t.trim()}`);
  }
  if (type === "source") {
    if (args.resource) lines.push(`resource: "${args.resource}"`);
    else if (ext) lines.push(`resource: "./raw/${args.subdir || ""}/${args.slug}.${ext}"`);
  } else {
    // analysis / comparison / synthesis 多源用 sources[]
    if (args.sources_used) {
      lines.push("sources_used:");
      for (const s of args.sources_used.split(",")) lines.push(`  - ${s.trim()}`);
    }
    // analysis 专属必填字段(对齐 page-analysis.md L32-37)
    if (type === "analysis" && args.answer_to) {
      lines.push(`answer_to: "${args.answer_to}"`);
    }
    // analysis / comparison / synthesis 必填 sources_count
    if (args.sources_count) {
      lines.push(`sources_count: ${args.sources_count}`);
    } else if (args.sources_used) {
      // 没显式传 → 用 sources_used 数组长度
      lines.push(`sources_count: ${args.sources_used.split(",").length}`);
    }
  }
  lines.push("generated:");
  lines.push(`  by: "producer/aeps-llm-wiki-plugin/${readPluginVersion()}"`);
  lines.push(`  at: "${now}"`);
  lines.push(`status: stable`);
  if (args.stale_after) lines.push(`stale_after: "${args.stale_after}"`);
  if (type === "source") {
    if (args.source_file) lines.push(`source_file: "${args.source_file}"`);
    lines.push(`format: ${ext || "md"}`);
    lines.push(`converter: ${converter}`);
    lines.push(`native_text: ${native}`);
    lines.push(`converted_path: ${converted === null || converted === "null" ? "null" : `"${converted}"`}`);
  }
  lines.push(`updated: "${now}"`);
  if (args.summary) lines.push(`summary: "${args.summary}"`);
  lines.push("---");
  return lines.join("\n");
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

  const fm = renderFrontmatter(type, args);
  const body = renderBody(type, tpl, args);
  const out = fm + "\n" + body;

  // 输出路径:knowledge/{TYPE_TO_DIR}/{slug}.md 或 --out 指定
  // 用户工程根用上面解析的 projectRoot,与 templates 路径同源
  const outPath = args.out
    ? resolve(args.out)
    : resolve(projectRoot, "knowledge", TYPE_TO_DIR[type], `${args.slug}.md`);
  mkdirSync(dirname(outPath), { recursive: true });
  try {
    writeFileSync(outPath, out, "utf8");
  } catch (e) {
    console.error(`ERROR: write failed: ${outPath}: ${e.message}`);
    process.exit(3);
  }
  console.log(`OK: ${type} → ${outPath} (${out.length} bytes)`);
}

main();