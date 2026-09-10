// aggregate-index.js — 扫 knowledge/**/*.md → 聚合生成 index.md / overview.md / glossary.md
// PRD §4.1.1:确定性脚本聚合目录,不依赖 LLM.
//
// 用法:
//   node aggregate-index.js [--knowledge ./knowledge] [--dry-run] [--json]
//
// 行为:
//   - 扫 {knowledge}/*.md 之外的子目录(sources/, entities/*, concepts/*, analyses/, comparisons/, syntheses/)
//   - 读 frontmatter (type / title / description / tags / id / aliases),不动正文
//   - 按 type + 子类聚合,生成 knowledge/index.md
//   - 生成/追加 knowledge/glossary.md(从 title + aliases 抽取术语条目;不覆盖用户已写条目)
//   - v0.6.2 起 **不再** 写入 knowledge/overview.md:overview 改由 LLM 在 ingest 大图变化时维护,
//     骨架来自 plugin 仓 `doc/template/page-overview.md`(见 scripts/init/build-skeleton.js)
//   - 输出 mtime,幂等;同状态连跑两次产物相同
//
// JSON stdout 增量(P2-3 批次 3):
//   - scanned: <number>
//   - by_type: { 'entity.person': 3, 'concept.field': 4, source: 2, ... }
//   - by_subdir: { 'sources': 2, 'entities/person': 3, ... }  (可选)
// --json 显式开启;不带 --json 时 stdout 仍是人类可读 "scanned N pages from ..."
//
// exit: 0 OK / 1 参数错 / 2 缺依赖
//
// change history:
//   - 0.6.6 (PR-B #28/#29/#31): 渲染约定统一 ——
//       (1) 抽 renderTagsLineSuffix(fm, {showTags}) 共用于 source / entity / concept /
//           analysis / comparison / synthesis 6 处(对齐 #31,消除 3 处重复);默认 showTags=false,
//           行尾 <span style="color:gray">#tag</span> 不渲染(对齐 #28,默认按选项 A);
//           新增 --show-tags CLI 开关恢复旧行为(兼容 #31)。
//       (2) renderGlossaryDynamic 按术语首字母分组输出 ## A / ## B / ... / ## Z,
//           中文术语归 ## 中文,数字术语归 ## 0-9,空字母节省略(对齐 #29 + page-glossary.md 模板)。
//       (3) page-index.md / page-glossary.md / SKILL.md 步骤 14/15 同步约定;scripts/test/
//           aggregate-index.test.js 改 4 个旧 case + 加 4 个新 case 覆盖默认关 / --show-tags /
//           glossary A-Z / glossary 中文 / 空字母节省略。
//   - 0.6.0: P0-#3 (issue #3) — index.md / overview.md / glossary.md 注入最小 frontmatter
//     (type/title/updated/generated/status/tags)。旧版只有 `---` 水平线,lint R7.2 fail。
//     ⚠ 此修复过度泛化,踩到 OKF §3.2 reserved filenames(index.md/log.md) 与 plugin 扩展
//     reserved filenames(glossary.md/overview.md),见 §3.3 frontmatter-spec.md。
//   - 0.6.2: 移除 overview.md 写入。overview 由 LLM 按 doc/template/page-overview.md 骨架维护,
//     聚合脚本不再覆写(避免 LLM 大图被计数列表覆盖)。
//   - 0.6.3 (issue #5 fix):index.md / glossary.md 停止注入 frontmatter(对齐 OKF §3.2 +
//     frontmatter-spec.md §3.3 的 reserved-filename 约定)。改为读
//     `doc/template/page-{index,glossary}.md` 骨架 + 变量替换 `{plugin 版本}` / `{最近更新}`。
//     触发链:lint R7.1/R7.2 未豁免 reserved filename → ingest SKILL 步骤 19 FAIL →
//     用户/agent 反向给 reserved file 补 frontmatter 才过 → 污染 reserved file
//     (本次同步修 lint-stub.js 加 R7.3 检测 + reserved 豁免)。
//   - 0.6.4 (issue #5 fix 续):doc/template/page-{index,glossary}.md 模板里的硬编码占位 wikilink / 术语
//     全部清空为「*(暂无)*」(同时删除 Entities/Concepts 节里 ### Person/Method/... H3 占位,
//     改为脚本 renderIndex/renderGlossary 按 type 动态生成,避免双重 H3)。
//   - (issue #11 fix):init 模板动态区改用 AGGREGATE-START / AGGREGATE-END HTML 注释标记对包住
//     (sentinel 方案)。写入规则:
//       1) 目标文件含标记对 → 只整体替换两个标记之间的动态区,标记外的手写区(Overview /
//          维护备注 / 手工术语)原样保留;
//       2) 目标文件不含标记对(存量 wiki)→ 保持 0.6.4 行为:按模板 + 动态区全量重建,
//          产物剥掉标记行(不迁移、不把存量文件 sentinel 化);
//       3) 目标文件不存在 → 以模板为底、动态区填入标记之间(模板无标记对时退回 2)。
//     动态区自含 H2 标题(## Sources / ## Entities / ## Concepts / ## Analyses / ## Comparisons /
//     ## Syntheses),Entities / Concepts 新增带计数的 H2(占位 H2 随首次聚合被替换,不再并存)。

import { readFileSync, writeFileSync, readdirSync, mkdirSync, existsSync, statSync } from "node:fs";
import { resolve, dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { requireDeps } from "./lib/preflight.js";
// 批次 3 P1-6: inline preflight 先跑;缺包 → throw 含精确 npm install 命令
await requireDeps({ "js-yaml": "js-yaml" });
// 动态 import:必须在 requireDeps 之后
const yaml = (await import("js-yaml")).default;

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---- (issue #11 fix)sentinel 动态区标记 ----
// init 模板(doc/template/page-{index,glossary}.md + build-skeleton 内联模板)把「会被聚合脚本
// 整体重写的动态区」包在两个 HTML 注释标记之间;标记之外是 LLM / 用户手写区,脚本永不触碰。
const AGGREGATE_START = "<!-- AGGREGATE-START -->";
const AGGREGATE_END = "<!-- AGGREGATE-END -->";

/** text 是否含一对完整的 START...END 标记(且 START 在前) */
function hasSentinelPair(text) {
  const s = text.indexOf(AGGREGATE_START);
  if (s < 0) return false;
  return text.indexOf(AGGREGATE_END, s + AGGREGATE_START.length) > s;
}

/**
 * 把 text 中两个标记之间的全部内容替换为 body;无完整标记对时返回 null(调用方退回 legacy 路径)。
 * 标记行本身保留,输出形态:START 换行 + body + 空行 + END...
 */
function replaceSentinelRegion(text, body) {
  const s = text.indexOf(AGGREGATE_START);
  if (s < 0) return null;
  const e = text.indexOf(AGGREGATE_END, s + AGGREGATE_START.length);
  if (e < 0) return null;
  const head = text.slice(0, s) + AGGREGATE_START + "\n";
  const tail = text.slice(e);
  return head + body.replace(/\r?\n+$/, "") + "\n\n" + tail;
}

/** 剥掉包含标记的整行(legacy 输出保持 0.6.4 形态,存量文件不被 sentinel 化) */
function stripSentinelMarkerLines(text) {
  return text
    .split("\n")
    .filter((l) => !l.includes(AGGREGATE_START) && !l.includes(AGGREGATE_END))
    .join("\n");
}

const TYPE_DIRS = [
  ["source", "sources"],
  ["entity.person", "entities/person"],
  ["entity.organization", "entities/organization"],
  ["entity.project", "entities/project"],
  ["entity.product", "entities/product"],
  ["entity.event", "entities/event"],
  ["entity.place", "entities/place"],
  ["entity.other", "entities/other"],
  ["concept.theory", "concepts/theory"],
  ["concept.method", "concepts/method"],
  ["concept.field", "concepts/field"],
  ["concept.phenomenon", "concepts/phenomenon"],
  ["concept.standard", "concepts/standard"],
  ["concept.term", "concepts/term"],
  ["concept.other", "concepts/other"],
  ["analysis", "analyses"],
  ["comparison", "comparisons"],
  ["synthesis", "syntheses"],
];

// ---- frontmatter 解析(只抽字段,不严格校验;lint 负责强校验) ----
function parseFrontmatter(mdText) {
  const m = mdText.match(/^---\s*\n([\s\S]*?)\n---\s*\n/);
  if (!m) return {};
  try {
    return yaml.load(m[1]) || {};
  } catch {
    return {};
  }
}

function walk(rootDir, subRel) {
  const abs = join(rootDir, subRel);
  if (!existsSync(abs)) return [];
  return readdirSync(abs)
    .filter((f) => f.endsWith(".md") && !f.startsWith(".") && f !== "README.md")
    .map((f) => {
      const full = join(abs, f);
      const stat = statSync(full);
      return { file: full, rel: relative(rootDir, full), mtime: stat.mtimeMs };
    });
}

function loadAll(rootDir) {
  const out = [];
  for (const [type, dir] of TYPE_DIRS) {
    for (const f of walk(rootDir, dir)) {
      const md = readFileSync(f.file, "utf8");
      const fm = parseFrontmatter(md);
      out.push({
        type: fm.type || type,
        title: fm.title || f.rel.replace(/\.md$/, ""),
        description: fm.description || "",
        tags: fm.tags || [],
        aliases: fm.aliases || [],
        id: fm.id || f.rel.replace(/\.md$/, ""),
        resource: fm.resource || "",
        status: fm.status || "stable",
        rel: f.rel,
        mtime: f.mtime,
      });
    }
  }
  return out;
}

// v0.6.0 (issue #3 fix):聚合页(index/overview/glossary)缺 frontmatter → OKF §4 必填。
// 复用同一份最小 frontmatter 模板:type / title / updated / generated / status / tags
function renderAggregateFrontmatter(type, title) {
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  return [
    "---",
    `type: ${type}`,
    `title: "${title}"`,
    `updated: "${now}"`,
    `generated:`,
    `  by: "producer/aeps-llm-wiki-plugin/${readPluginVersion()}"`,
    `  at: "${now}"`,
    `status: stable`,
    `tags:`,
    `  - docform/${type}`,
    `  - domain/knowledge-management`,
    `  - layer/${type}`,
    `  - maturity/stable`,
    `  - phase/maintained`,
    "---",
    "",
  ].join("\n");
}

// readPluginVersion 与 gen-page.js 同源(plugin 本体 .claude-plugin/plugin.json),
// 但 aggregate-index.js 不读 plugin.json 时容易 fallback "0.0.0";这里独立内联解析。
function readPluginVersion() {
  const argv = process.argv.slice(2);
  const i = argv.indexOf("--plugin-root");
  const candidates = [];
  if (i >= 0) candidates.push(resolve(argv[i + 1], ".claude-plugin", "plugin.json"));
  if (process.env.CLAUDE_PLUGIN_ROOT) candidates.push(resolve(process.env.CLAUDE_PLUGIN_ROOT, ".claude-plugin", "plugin.json"));
  candidates.push(resolve(__dirname, "..", ".claude-plugin", "plugin.json"));
  for (const p of candidates) {
    if (!existsSync(p)) continue;
    try {
      const j = JSON.parse(readFileSync(p, "utf8"));
      if (j.version) return j.version;
    } catch { /* fallthrough */ }
  }
  return "unknown";
}

// v0.6.3: reserved filenames(index.md / glossary.md)改读 doc/template/page-{index,glossary}.md
// 骨架 + 变量替换,不再注入 frontmatter(对齐 OKF §3.2 + frontmatter-spec.md §3.3)。
// 候选链与 gen-page.js / build-skeleton.js 同构(--plugin-root > $CLAUDE_PLUGIN_ROOT > __dirname 上溯)。
function resolveTemplateCandidates(name) {
  const argv = process.argv.slice(2);
  const i = argv.indexOf("--plugin-root");
  const out = [];
  if (i >= 0) out.push(resolve(argv[i + 1], "doc", "template", name));
  if (process.env.CLAUDE_PLUGIN_ROOT) out.push(resolve(process.env.CLAUDE_PLUGIN_ROOT, "doc", "template", name));
  out.push(resolve(__dirname, "..", "doc", "template", name));
  return out;
}

// ponytail: 只替换两行元信息(模板 `**plugin 版本**:X.Y.Z` / `**最近更新**:ISO 8601` 两行尾部的值),
// 模板保留默认值(开箱即用,不依赖脚本),脚本做整行尾部值替换。
// 模板里 {数量} 形式的大括号占位符由 renderIndex/renderGlossary 循环拼实际计数(避免"所有 H2 节显示同一个数")。
function loadTemplateAndReplaceVars(name, vars) {
  const candidates = resolveTemplateCandidates(name);
  for (const p of candidates) {
    if (!existsSync(p)) continue;
    let tpl = readFileSync(p, "utf8");
    // 整行匹配,避免误伤正文里的 "plugin 版本" 字样
    tpl = tpl.replace(/^> \*\*plugin 版本\*\*:.+$/m, `> **plugin 版本**:${vars.pluginVersion}`);
    tpl = tpl.replace(/^> \*\*最近更新\*\*:.+$/m, `> **最近更新**:${vars.now}`);
    return tpl;
  }
  throw new Error(
    `无法定位模板 ${name};候选路径都试过:\n  - ${candidates.join("\n  - ")}\n` +
    `请确认 plugin 仓 doc/template/ 下存在 ${name},或用 --plugin-root / $CLAUDE_PLUGIN_ROOT 显式指定。`
  );
}

// PR-B (issue #31) 抽 renderTagsLineSuffix:6 处 tags 行尾渲染共用一个函数;
// 默认 showTags=false → 返回 "" 关闭行尾 tags(#28 推荐方案);
// --show-tags 开启时返回 ' <span style="color:gray">#tag1 #tag2</span>' (#31 兼容旧行为)。
function renderTagsLineSuffix(fm, { showTags }) {
  if (!showTags) return "";
  const tagStr = (fm.tags || []).map((t) => `#${t.split("/").pop()}`).join(" ");
  return tagStr ? ` <span style="color:gray">${tagStr}</span>` : "";
}

// PR-B (issue #29) glossary 字母节分组:中文术语归 ## 中文,数字归 ## 0-9;
// 大小写不敏感(Apple/apple 都归 ## A);空字母节省略。
function bucketKey(letter) {
  const c = (letter || "").toLowerCase();
  if (/[a-z]/.test(c)) return c.toUpperCase();
  if (/[一-鿿]/.test(letter || "")) return "中文";
  if (/[0-9]/.test(c)) return "0-9";
  return "其他";
}

// (issue #11 fix)动态区自含 H2 标题:占位 H2(## Sources({数量}) 等)随模板 sentinel 区间
// 被整体替换,所以 Entities / Concepts 在这里补上带计数的 H2(0.6.4 依赖模板占位 H2,不再可用)。
// PR-B (issue #28/#31):接受 {showTags},3 处 tags 行尾渲染统一走 renderTagsLineSuffix。
function renderIndexDynamic(pages, { showTags = false } = {}) {
  const lines = [];
  // Sources 按 frontmatter `resource` 路径解析的 raw/{subdir}/ 分组;子目录名去 \d+_ 前缀
  // 每条 [[wikilink|alias]] + frontmatter status + tags(直接来自 source,不做包装)
  const sources = pages.filter((p) => p.type === "source");
  if (!sources.length) {
    lines.push("## Sources (0)");
    lines.push("");
    lines.push("*(暂无)*");
    lines.push("");
  } else {
    // 按 resource 路径的 raw/{subdir}/ 段分组;无法解析的进「其他」
    const groups = new Map();
    for (const p of sources) {
      const subdir = parseRawSubdir(p.resource);
      const key = subdir || "其他";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(p);
    }
    // 按子目录名排序;「其他」放最后
    const sortedKeys = [...groups.keys()].sort((a, b) => {
      if (a === "其他") return 1;
      if (b === "其他") return -1;
      return a.localeCompare(b);
    });
    const total = sources.length;
    lines.push(`## Sources (${total})`);
    lines.push("");
    for (const key of sortedKeys) {
      const items = groups.get(key);
      lines.push(`### ${key} (${items.length})`);
      lines.push("");
      for (const p of items.sort((a, b) => a.title.localeCompare(b.title))) {
        lines.push(`- ${renderSourceLine(p, { showTags })}`);
      }
      lines.push("");
    }
  }

  // Entities / Concepts:先输出带总计数的 H2,再按子类输出 H3(与模板占位 H2 一一对应)
  for (const [label, prefix] of [["Entities", "entity."], ["Concepts", "concept."]]) {
    const subtypes = TYPE_DIRS.filter(([t]) => t.startsWith(prefix));
    let groupTotal = 0;
    for (const [type] of subtypes) groupTotal += pages.filter((p) => p.type === type).length;
    lines.push(`## ${label} (${groupTotal})`);
    lines.push("");
    for (const [type] of subtypes) {
      const sub = type.split(".")[1];
      const items = pages.filter((p) => p.type === type);
      lines.push(`### ${sub.charAt(0).toUpperCase() + sub.slice(1)} (${items.length})`);
      lines.push("");
      if (!items.length) {
        lines.push("*(暂无)*");
      } else {
        for (const p of items.sort((a, b) => a.title.localeCompare(b.title))) {
          lines.push(`- [${p.title}](./${p.rel.replace(/\\/g, "/")}) —— ${p.description}${renderTagsLineSuffix(p, { showTags })}`);
        }
      }
      lines.push("");
    }
  }

  for (const [type] of TYPE_DIRS.filter(([t]) => ["analysis", "comparison", "synthesis"].includes(t))) {
    // analysis/comparison/synthesis 都是复数集合,标题就用原名 + count
    const label = type.charAt(0).toUpperCase() + type.slice(1);
    const items = pages.filter((p) => p.type === type);
    lines.push(`## ${label} (${items.length})`);
    lines.push("");
    if (!items.length) {
      lines.push("*(暂无)*");
    } else {
      const sortFn = type === "analysis"
        ? (a, b) => b.mtime - a.mtime
        : (a, b) => a.title.localeCompare(b.title);
      for (const p of items.sort(sortFn)) {
        lines.push(`- [${p.title}](./${p.rel.replace(/\\/g, "/")}) —— ${p.description}${renderTagsLineSuffix(p, { showTags })}`);
      }
    }
    lines.push("");
  }
  return lines;
}

// legacy 路径(issue #11 兼容分支):模板整份(header,剥掉 sentinel 标记行)+
// 动态区追加 —— 与 0.6.4 输出形态一致,用于「目标文件无标记对」的存量 wiki。
// PR-B (issue #28/#31):接受 {showTags} 透传给 renderIndexDynamic。
function renderIndex(rootDir, pages, { showTags = false } = {}) {
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const vars = { pluginVersion: readPluginVersion(), now };
  // v0.6.3: 模板 header 替代 frontmatter push;模板自身已含 H1 / 提示注释 / auto-gen 段
  const header = stripSentinelMarkerLines(loadTemplateAndReplaceVars("page-index.md", vars));
  return header + "\n" + renderIndexDynamic(pages, { showTags }).join("\n");
}

// 从 frontmatter resource 路径解析 raw/{subdir}/ 段;返回子目录名(去掉 \d+_ 前缀);无法解析返回 null
function parseRawSubdir(resource) {
  if (!resource || typeof resource !== "string") return null;
  // 支持 ./raw/{subdir}/{file} 或 raw/{subdir}/{file} 或 /raw/{subdir}/{file}
  const m = resource.match(/(?:\.?\/?)raw\/([^/]+)\//);
  if (!m) return null;
  // 去编号前缀: 06_功能安全 → 功能安全
  return m[1].replace(/^\d+_/, "");
}

// 渲染一条 source 行:[[wikilink|alias]] —— description [{status}] {tag1} {tag2} ...
// PR-B (issue #28/#31):接受 {showTags};行尾 tags 渲染统一走 renderTagsLineSuffix。
function renderSourceLine(p, { showTags = false } = {}) {
  // 裸文件名 = p.rel 去掉 sources/ 前缀和 .md 后缀;统一正斜杠(Obsidian wikilink 要求)
  const basename = p.rel.replace(/\\/g, "/").replace(/^sources\//, "").replace(/\.md$/, "");
  const alias = p.title || basename;
  const link = `[[${basename}|${alias}]]`;
  const desc = p.description ? ` —— ${p.description}` : "";
  const status = p.status ? ` [${p.status}]` : "";
  const tagsSuffix = renderTagsLineSuffix(p, { showTags });
  return `${link}${desc}${status}${tagsSuffix}`;
}

// ponytail: v0.6.2 起 overview.md 改由 LLM 在 ingest 大图变化时维护,聚合脚本不再覆写。
// 计数信息已迁移到 index.md(sources / entities / concepts / syntheses / comparisons / analyses
// 各自一节,带 type · count),所以保留 `renderOverview` 仅在 json 模式下供 stdout 调试输出。
function renderOverview(pages) {
  const lines = [];
  for (const [type, dir] of TYPE_DIRS) {
    const items = pages.filter((p) => p.type === type);
    const label = type.replace(".", " · ");
    lines.push(`- **${label}**: ${items.length} 篇`);
  }
  return lines.join("\n");
}

// (issue #11 fix)glossary 动态区:title + aliases 抽取术语条目,按首字母分组到 ## A / ## B / ... H2 节
// PR-B (issue #29):中文术语归 ## 中文,数字术语归 ## 0-9,空字母节省略(对齐 page-glossary.md 模板)。
function renderGlossaryDynamic(pages, { showTags: _showTags = false } = {}) {
  const lines = [];
  const seen = new Map();
  for (const p of pages) {
    const terms = [p.title, ...(p.aliases || [])].filter(Boolean);
    for (const t of terms) {
      if (!seen.has(t.toLowerCase())) seen.set(t.toLowerCase(), { term: t, page: p });
    }
  }
  const entries = [...seen.values()].sort((a, b) => a.term.localeCompare(b.term));
  if (!entries.length) {
    lines.push("*(暂无)*");
    return lines;
  }
  // 按 bucketKey 分组
  const buckets = new Map();
  for (const e of entries) {
    const firstChar = [...e.term][0] || "";
    const key = bucketKey(firstChar);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(e);
  }
  // 输出顺序:A-Z (字母序),然后 ## 中文,然后 ## 0-9,然后 ## 其他
  const order = (k) => {
    if (k === "中文") return "Z+1";
    if (k === "0-9") return "Z+2";
    if (k === "其他") return "Z+3";
    return k;
  };
  const sortKeys = [...buckets.keys()].sort((a, b) => order(a).localeCompare(order(b)));
  for (const key of sortKeys) {
    lines.push(`## ${key}`);
    lines.push("");
    for (const e of buckets.get(key)) {
      lines.push(`- **${e.term}** —— 参见 [${e.page.title}](./${e.page.rel.replace(/\\/g, "/")}):${e.page.description}`);
    }
    lines.push("");
  }
  return lines;
}

// legacy 路径(issue #11 兼容分支):与 0.6.4 输出形态一致(模板 header 剥标记行 + 动态区追加)
function renderGlossary(pages) {
  // 简单词典:每页 title + aliases 作为术语,首次出现的写一份;不覆盖用户已有条目
  const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const vars = { pluginVersion: readPluginVersion(), now };
  // v0.6.3: 模板 header 替代 frontmatter push
  const header = stripSentinelMarkerLines(loadTemplateAndReplaceVars("page-glossary.md", vars));
  return header + "\n" + renderGlossaryDynamic(pages).join("\n") + "\n";
}

// (issue #11 fix)组装 index.md / glossary.md 最终写入内容:
//   1) 目标文件存在且含标记对 → 只替换标记之间的动态区,手写区保留;
//   2) 目标文件存在但无标记对 → legacy(0.6.4)全量重建,产物不引入标记;
//   3) 目标文件不存在 → 以模板为底、动态区填入标记之间(模板无标记对时退回 legacy)。
function composeAggregateDoc(targetPath, templateName, vars, dynamicLines, legacyRender) {
  const dynamic = dynamicLines.join("\n");
  if (existsSync(targetPath)) {
    const existing = readFileSync(targetPath, "utf8");
    const patched = replaceSentinelRegion(existing, dynamic);
    if (patched !== null) return patched;
    return legacyRender();
  }
  const tpl = loadTemplateAndReplaceVars(templateName, vars);
  const filled = replaceSentinelRegion(tpl, dynamic);
  return filled !== null ? filled : legacyRender();
}

function mergePreserveUserEntries(existingPath, newContent) {
  if (!existsSync(existingPath)) return newContent;
  const existing = readFileSync(existingPath, "utf8");
  // 简单策略:扫描 "## " 节标题,若新内容有同标题 → 保留旧节;若新内容独有 → 追加
  const sectionRe = /^## (.+?)\n([\s\S]*?)(?=\n## |\n*$)/gm;
  const existingSections = new Map();
  let m;
  while ((m = sectionRe.exec(existing)) !== null) existingSections.set(m[1].trim(), m[2]);
  return newContent; // MVP:不深度合并,直接覆盖;后续 --fix 模式做精细合并
}

function main() {
  const args = process.argv.slice(2);
  const knowledge = (() => {
    const i = args.indexOf("--knowledge");
    return i >= 0 ? resolve(args[i + 1]) : resolve(process.cwd(), "knowledge");
  })();
  const dryRun = args.includes("--dry-run");
  const jsonMode = args.includes("--json");
  // PR-B (issue #28/#31):--show-tags 开关;默认 false → 行尾 <span> tags 不渲染。
  // v0.6.7 (issue #32):默认翻转为 true —— index.md 行尾 tags 是 query 工作流步骤 1.2
  // 「按 tags 关键词 grep 过滤候选页」的数据源,默认关闭把这条检索路径断了;
  // --no-tags 恢复 PR-B 默认关行为(--show-tags 保留,等价默认)。
  const showTags = !args.includes("--no-tags");

  if (!existsSync(knowledge)) {
    console.error(`ERROR: knowledge 目录不存在: ${knowledge}`);
    process.exit(1);
  }

  const pages = loadAll(knowledge);

  // P2-3 批次 3: by_type 分类统计 + by_subdir 子目录统计
  const byType = {};
  const bySubdir = {};
  for (const p of pages) {
    const t = p.type || "unknown";
    byType[t] = (byType[t] || 0) + 1;
    // subdir = 第一层目录(sources / entities / concepts / analyses / ...);顶层页如 index/overview 归 "root"
    const rel = p.rel.replace(/\\/g, "/");
    const subdir = rel.includes("/") ? rel.split("/")[0] : "root";
    bySubdir[subdir] = (bySubdir[subdir] || 0) + 1;
  }

  // (issue #11 fix)index.md / glossary.md 组装:sentinel 区间替换或 legacy 全量重建(见 composeAggregateDoc)
  const composeWrites = () => {
    const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    const vars = { pluginVersion: readPluginVersion(), now };
    const idxPath = join(knowledge, "index.md");
    const glPath = join(knowledge, "glossary.md");
    const idx = composeAggregateDoc(idxPath, "page-index.md", vars, renderIndexDynamic(pages, { showTags }), () => renderIndex(knowledge, pages, { showTags }));
    const gl = composeAggregateDoc(glPath, "page-glossary.md", vars, renderGlossaryDynamic(pages, { showTags }), () => renderGlossary(pages));
    // ponytail: v0.6.2+ overview.md 不再写入,见 renderOverview 注释
    return [
      [idxPath, idx],
      [glPath, gl],
    ];
  };

  if (jsonMode) {
    const out = {
      knowledge: knowledge.replace(/\\/g, "/"),
      scanned: pages.length,
      dry_run: dryRun,
      by_type: byType,
      by_subdir: bySubdir,
      written: [],
    };
    const writes = composeWrites();
    for (const [p, c] of writes) {
      if (dryRun) {
        out.written.push({ file: p.replace(/\\/g, "/"), bytes: c.length, dry_run: true });
      } else {
        mkdirSync(dirname(p), { recursive: true });
        writeFileSync(p, c, "utf8");
        out.written.push({ file: p.replace(/\\/g, "/"), bytes: c.length });
      }
    }
    console.log(JSON.stringify(out, null, 2));
    return;
  }

  // 默认人类可读 stdout(向后兼容)
  console.log(`scanned ${pages.length} pages from ${knowledge}`);

  const writes = composeWrites();

  for (const [p, c] of writes) {
    if (dryRun) {
      console.log(`[dry-run] would write: ${p} (${c.length} bytes)`);
    } else {
      mkdirSync(dirname(p), { recursive: true });
      writeFileSync(p, c, "utf8");
      console.log(`OK: ${p} (${c.length} bytes)`);
    }
  }
}

main();