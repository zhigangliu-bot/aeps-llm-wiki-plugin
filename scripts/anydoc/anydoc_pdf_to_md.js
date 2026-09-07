/**
 * Convert PDF → markdown via @firecrawl/anydoc CLI.
 *
 * Wraps the converted output with the wiki-plugin frontmatter spec
 * (see doc/schema/frontmatter-spec.md). Output is a `.md` file with
 * `type: source`, ready for ingest skill to move into `raw/`.
 *
 * Usage:
 *   node anydoc_pdf_to_md.js <file.pdf> [-o out.md]
 *
 * 仅接受 .pdf:docx / pptx / xlsx 走 docling_to_md.py(docling 路径)。
 * 见 README.md。
 */
import { readFileSync, writeFileSync, statSync, existsSync } from "node:fs";
import { extname, basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRIPTS_ROOT = resolve(__dirname, "..");

const SUPPORTED = new Set([".pdf"]);

function findAnydocBin() {
  // 优先用本地 node_modules/.bin(anydoc.cmd on Windows),
  // 拷给用户免装全局 npm。
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
  if (r.status === 3) {
    throw new Error(
      `anydoc 不处理扫描件 PDF (exit 3)。需先转图片再走 OCR:\n` +
        `  pdftoppm "${input}" page -png\n` +
        `  python ../ocr/ocr_to_md.py page-1.png`
    );
  }
  throw new Error(r.stderr || r.error?.message || `anydoc exit=${r.status}`);
}

// ponytail: frontmatter 由 wiki-plugin ingest skill 在入库时补,
// 脚本只负责把任意文件转成 md 文本,忠于原文格式。
function toMarkdown(_input, mdBody) {
  return mdBody.trimEnd() + "\n";
}

function parseArgs(argv) {
  const args = { input: null, out: null };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "-o" || a === "--out") {
      args.out = argv[++i];
    } else if (!args.input) {
      args.input = a;
    }
  }
  return args;
}

function main() {
  const { input, out } = parseArgs(process.argv);
  if (!input) {
    console.error(
      "usage: node anydoc_pdf_to_md.js <file.pdf> [-o out.md]\n"
      + "docx/pptx/xlsx 走 docling_to_md.py(docling 路径)"
    );
    process.exit(2);
  }
  const ext = extname(input).toLowerCase();
  if (!SUPPORTED.has(ext)) {
    console.error(
      `ERROR: unsupported extension '${ext}', supported: ${[...SUPPORTED].join(", ")}`
    );
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
  writeFileSync(outPath, toMarkdown(input, body), "utf8");
  const lines = body.split("\n").length;
  console.log(`OK: ${lines} lines -> ${outPath}`);
}

try {
  main();
} catch (err) {
  console.error("FAIL:", err?.message ?? err);
  process.exit(1);
}
