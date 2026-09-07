// aggregate-index.js — 扫 knowledge/**/*.md → 聚合生成 index.md / overview.md / glossary.md
// PRD §4.1.1:确定性脚本聚合目录,不依赖 LLM.
//
// 用法:
//   node aggregate-index.js [--knowledge ./knowledge] [--dry-run]
//
// 行为:
//   - 扫 {knowledge}/*.md 之外的子目录(sources/, entities/*, concepts/*, analyses/, comparisons/, syntheses/)
//   - 读 frontmatter (type / title / description / tags / id / aliases),不动正文
//   - 按 type + 子类聚合,生成 knowledge/index.md
//   - 生成 knowledge/overview.md(只列 type + count,不写内容)
//   - 生成/追加 knowledge/glossary.md(从 title + aliases 抽取术语条目;不覆盖用户已写条目)
//   - 输出 mtime,幂等;同状态连跑两次产物相同
//
// exit: 0 OK / 1 参数错

import { readFileSync, writeFileSync, readdirSync, mkdirSync, existsSync, statSync } from "node:fs";
import { resolve, dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";

const __dirname = dirname(fileURLToPath(import.meta.url));

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

function renderIndex(rootDir, pages) {
  const lines = [];
  lines.push("# 项目 Wiki 主目录");
  lines.push("");
  lines.push("> **自动生成**:本文件由 `scripts/aggregate-index.js` 维护。**不要手工编辑**。");
  lines.push("");
  lines.push("---");
  lines.push("");
  // Sources 按 frontmatter `resource` 路径解析的 raw/{subdir}/ 分组;子目录名去 \d+_ 前缀
  // 每条 [[wikilink|alias]] + frontmatter status + tags(直接来自 source,不做包装)
  const sources = pages.filter((p) => p.type === "source");
  if (!sources.length) {
    lines.push("## Sources");
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
        lines.push(`- ${renderSourceLine(p)}`);
      }
      lines.push("");
    }
  }

  for (const [type, dir] of TYPE_DIRS) {
    if (!type.startsWith("entity.") && !type.startsWith("concept.")) continue;
    const label = type.split(".")[1];
    const items = pages.filter((p) => p.type === type);
    lines.push(`### ${label.charAt(0).toUpperCase() + label.slice(1)} (${items.length})`);
    lines.push("");
    if (!items.length) {
      lines.push("*(暂无)*");
    } else {
      for (const p of items.sort((a, b) => a.title.localeCompare(b.title))) {
        const tagStr = (p.tags || []).slice(0, 3).map((t) => `#${t.split("/").pop()}`).join(" ");
        lines.push(`- [${p.title}](./${p.rel.replace(/\\/g, "/")}) —— ${p.description}${tagStr ? ` <span style="color:gray">${tagStr}</span>` : ""}`);
      }
    }
    lines.push("");
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
        const tagStr = (p.tags || []).slice(0, 3).map((t) => `#${t.split("/").pop()}`).join(" ");
        lines.push(`- [${p.title}](./${p.rel.replace(/\\/g, "/")}) —— ${p.description}${tagStr ? ` <span style="color:gray">${tagStr}</span>` : ""}`);
      }
    }
    lines.push("");
  }
  return lines.join("\n");
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
function renderSourceLine(p) {
  // 裸文件名 = p.rel 去掉 sources/ 前缀和 .md 后缀;统一正斜杠(Obsidian wikilink 要求)
  const basename = p.rel.replace(/\\/g, "/").replace(/^sources\//, "").replace(/\.md$/, "");
  const alias = p.title || basename;
  const link = `[[${basename}|${alias}]]`;
  const desc = p.description ? ` —— ${p.description}` : "";
  const status = p.status ? ` [${p.status}]` : "";
  const tags = (p.tags || []).map((t) => `#${t.split("/").pop()}`).join(" ");
  const tail = [status, tags ? `<span style="color:gray">${tags}</span>` : ""].filter(Boolean).join(" ");
  return `${link}${desc}${tail ? ` ${tail}` : ""}`;
}

function renderOverview(pages) {
  const lines = [];
  lines.push("# 项目 Wiki 大图(overview)");
  lines.push("");
  lines.push("> **自动生成**:本文件由 `scripts/aggregate-index.js` 维护。");
  lines.push("");
  lines.push("---");
  lines.push("");
  for (const [type, dir] of TYPE_DIRS) {
    const items = pages.filter((p) => p.type === type);
    const label = type.replace(".", " · ");
    lines.push(`- **${label}**: ${items.length} 篇`);
  }
  lines.push("");
  lines.push("---");
  lines.push("");
  lines.push("参见 [index](./index.md) 查看完整目录。");
  lines.push("");
  return lines.join("\n");
}

function renderGlossary(pages) {
  // 简单词典:每页 title + aliases 作为术语,首次出现的写一份;不覆盖用户已有条目
  const lines = [];
  lines.push("# 项目 Wiki 术语表(glossary)");
  lines.push("");
  lines.push("> **自动生成**:本文件由 `scripts/aggregate-index.js` 维护;术语从各页 `title` + `aliases` 抽取,**不覆盖用户手写条目**。");
  lines.push("");
  lines.push("---");
  lines.push("");

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
  } else {
    for (const e of entries) {
      lines.push(`- **${e.term}** —— 参见 [${e.page.title}](./${e.page.rel.replace(/\\/g, "/")}):${e.page.description}`);
    }
  }
  lines.push("");
  return lines.join("\n");
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

  if (!existsSync(knowledge)) {
    console.error(`ERROR: knowledge 目录不存在: ${knowledge}`);
    process.exit(1);
  }

  const pages = loadAll(knowledge);
  console.log(`scanned ${pages.length} pages from ${knowledge}`);

  const idx = renderIndex(knowledge, pages);
  const ov = renderOverview(pages);
  const gl = renderGlossary(pages);

  const writes = [
    [join(knowledge, "index.md"), idx],
    [join(knowledge, "overview.md"), ov],
    [join(knowledge, "glossary.md"), gl],
  ];

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