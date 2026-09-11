/**
 * Convert office doc → markdown via @firecrawl/anydoc CLI.
 * 路径 3 office 第二优先级(RULES.md §1):pyoffice 失败后降级到这,
 * anydoc 也失败 → docling_to_md.py(最后兜底)。
 *
 * Usage:
 *   node anydoc_office_to_md.js <file.(docx|pptx|xlsx)> [-o out.md]
 */
import { writeFileSync, statSync, existsSync } from "node:fs";
import { extname, basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRIPTS_ROOT = resolve(__dirname, "..");

const SUPPORTED = new Set([".docx", ".pptx", ".xlsx"]);

function findAnydocBin() {
  // 优先本地 node_modules/.bin(anydoc.cmd on Windows)
  const local = join(SCRIPTS_ROOT, "node_modules", ".bin",
    process.platform === "win32" ? "anydoc.cmd" : "anydoc");
  if (existsSync(local)) return local;
  return "anydoc"; // fallback: PATH
}

function runAnydoc(input) {
  const bin = findAnydocBin();
  const r = spawnSync(bin, [input], {
    encoding: "utf8",
    maxBuffer: 200 * 1024 * 1024,
    windowsHide: true,
    shell: process.platform === "win32",
  });
  if (r.status === 0) return r.stdout;
  throw new Error(r.stderr || r.error?.message || `anydoc exit=${r.status}`);
}

function parseArgs(argv) {
  const args = { input: null, out: null };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "-o" || a === "--out") args.out = argv[++i];
    else if (!args.input) args.input = a;
  }
  return args;
}

function main() {
  const { input, out } = parseArgs(process.argv);
  if (!input) {
    console.error("usage: node anydoc_office_to_md.js <file.(docx|pptx|xlsx)> [-o out.md]");
    process.exit(2);
  }
  const ext = extname(input).toLowerCase();
  if (!SUPPORTED.has(ext)) {
    console.error(`ERROR: unsupported extension '${ext}', supported: ${[...SUPPORTED].join(", ")}`);
    process.exit(2);
  }
  if (!statSync(input, { throwIfNoEntry: false })?.isFile()) {
    console.error(`ERROR: not a file: ${input}`);
    process.exit(2);
  }

  const outPath = out
    ? resolve(out)
    : join(dirname(resolve(input)), `${basename(input, ext)}.md`);

  const body = runAnydoc(resolve(input));
  writeFileSync(outPath, body.trimEnd() + "\n", "utf8");
  console.log(`OK: ${body.split("\n").length} lines -> ${outPath}`);
}

try {
  main();
} catch (err) {
  console.error("FAIL:", err?.message ?? err);
  process.exit(1);
}
