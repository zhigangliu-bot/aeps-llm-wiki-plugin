#!/usr/bin/env node
/**
 * sync-files.js - Idempotent file sync from plugin to project per prd.md §4.1 sync table.
 *
 * Strategy mapping (per prd.md §4.1):
 *   - inbox/README.md              : overwrite (plugin current)
 *   - raw/README.md                : overwrite (plugin current)
 *   - templates/README.md          : overwrite (plugin current)
 *   - templates/page-*.md          : backfill missing; preserve existing
 *   - templates/tag-spec.md        : dictionary append (append-only, don't restore user deletions)
 *   - templates/concept-entities-spec.md : dictionary append
 *   - templates/rawdir-spec.md     : backfill missing; preserve existing
 *   - scripts/*                    : backfill missing; preserve existing
 *   - schema/*                     : overwrite (plugin current)
 *   - knowledge/index.md           : preserve (don't touch user content)
 *   - knowledge/overview.md        : preserve
 *   - knowledge/glossary.md        : preserve
 *   - knowledge/log.md             : append Init record (only on first creation, not on every re-run)
 *
 * Note: knowledge/log.md append-on-every-init would create duplication. The prd.md
 * sync table says "Append plugin-generated records, do not delete existing" — interpretation:
 * the Init record is written once at first creation (build-skeleton.js), and subsequent
 * re-runs do NOT re-append Init. (See SYNC-8: re-run preserves user-added log entries.)
 *
 * Usage:
 *   node scripts/init/sync-files.js --project <dir> --plugin-root <dir> [--dry-run]
 *
 * Exit codes: 0 success / 1 invalid args / 2 partial failure
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

function parseArgs(argv) {
  const args = { project: null, pluginRoot: null, dryRun: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--plugin-root') args.pluginRoot = argv[++i];
    else if (a === '--dry-run') args.dryRun = true;
  }
  if (!args.project || !args.pluginRoot) {
    console.error('Error: --project <dir> and --plugin-root <dir> are required');
    process.exit(1);
  }
  return args;
}

async function exists(p) {
  try { await fs.access(p); return true; } catch { return false; }
}

async function readText(p) {
  return await fs.readFile(p, 'utf8');
}

async function copyFile(src, dst, dryRun) {
  if (dryRun) return true;
  await fs.mkdir(path.dirname(dst), { recursive: true });
  await fs.copyFile(src, dst);
  return true;
}

// ponytail: dictionary append strategy. "Append new sections/items from plugin, do not restore user deletions."
// Implementation: find lines in plugin file that are NOT in project file (by line hash), append those
// to the end of the project file. Marker at the end keeps things traceable.
const DICT_MARKER = '\n\n<!-- aeps-llm-wiki-plugin:dictionary-append -->';

async function dictAppend(pluginContent, projectContent, dryRun, dst) {
  // ponytail: simple heuristic — split plugin content by H2 headers; for each H2 not present in
  // project content (by heading text), append that H2 block to project content. This is "best effort"
  // for line-based append; not a full markdown AST diff.
  const pluginH2s = splitByH2(pluginContent);
  const projectH2s = new Set(splitByH2(projectContent).map(b => b.heading));
  const newBlocks = pluginH2s.filter(b => !projectH2s.has(b.heading));
  if (newBlocks.length === 0) return false;
  const merged = projectContent.replace(/\s*$/, '') +
    DICT_MARKER + '\n\n' +
    newBlocks.map(b => b.text).join('\n\n');
  if (!dryRun) await fs.writeFile(dst, merged, 'utf8');
  return true;
}

function splitByH2(text) {
  // returns [{ heading, text }, ...] where heading is "## xxx" and text includes the heading line
  const lines = text.split(/\r?\n/);
  const blocks = [];
  let cur = null;
  for (const line of lines) {
    if (/^##\s+/.test(line)) {
      if (cur) blocks.push(cur);
      cur = { heading: line.trim(), text: line };
    } else if (cur) {
      cur.text += '\n' + line;
    } else {
      // content before first H2 — keep as "preamble" block
      if (!cur) cur = { heading: '', text: line };
      else cur.text += '\n' + line;
    }
  }
  if (cur && cur.text.trim()) blocks.push(cur);
  return blocks;
}

async function sync(args) {
  const project = path.resolve(args.project);
  const pluginRoot = path.resolve(args.pluginRoot);
  const dryRun = args.dryRun;
  const added = [];
  const updated = [];
  const skipped = [];
  const warned = [];

  // 1. inbox/README.md — overwrite from plugin doc/template/inbox-readme.md
  // ponytail: there's no inbox-readme.md in current template dir; copy rawdir-spec pattern.
  // We use a minimal inline template because plugin doc/template/ has no inbox-readme currently.
  // Strategy: if doc/template/inbox-readme.md exists in plugin, use it; else create inline.
  const inboxReadmeSrc = path.join(pluginRoot, 'doc', 'template', 'inbox-readme.md');
  const inboxReadmeDst = path.join(project, 'inbox', 'README.md');
  if (await exists(inboxReadmeSrc)) {
    await copyFile(inboxReadmeSrc, inboxReadmeDst, dryRun);
    if (await exists(inboxReadmeDst)) updated.push(inboxReadmeDst);
  }
  // ponytail: per prd.md SYNC-1 inbox/README.md is overwritten on every re-run.
  // Even without plugin source, on first creation it was created by build-skeleton.
  // Here we only run if plugin has the source — otherwise leave existing alone (skipped).

  // 2. raw/README.md — overwrite from plugin doc/template/rawdir-spec.md
  const rawReadmeSrc = path.join(pluginRoot, 'doc', 'template', 'rawdir-spec.md');
  const rawReadmeDst = path.join(project, 'raw', 'README.md');
  if (await exists(rawReadmeSrc)) {
    await copyFile(rawReadmeSrc, rawReadmeDst, dryRun);
    if (await exists(rawReadmeDst)) updated.push(rawReadmeDst);
  }

  // 3. templates/* — backfill missing; preserve existing (except README which overwrites)
  const tmplSrc = path.join(pluginRoot, 'doc', 'template');
  const tmplDst = path.join(project, 'templates');
  if (await exists(tmplSrc)) {
    const entries = await fs.readdir(tmplSrc, { withFileTypes: true });
    for (const e of entries) {
      if (!e.isFile()) continue;
      if (e.name === 'README.md') {
        // SYNC-3: overwrite README
        await copyFile(path.join(tmplSrc, e.name), path.join(tmplDst, e.name), dryRun);
        updated.push(path.join(tmplDst, e.name));
      } else if (e.name === 'tag-spec.md' || e.name === 'concept-entities-spec.md') {
        // SYNC-4: dictionary append
        const src = path.join(tmplSrc, e.name);
        const dst = path.join(tmplDst, e.name);
        if (await exists(dst)) {
          const changed = await dictAppend(await readText(src), await readText(dst), dryRun, dst);
          if (changed) updated.push(dst);
          else skipped.push(dst);
        } else {
          await copyFile(src, dst, dryRun);
          added.push(dst);
        }
      } else if (e.name.startsWith('page-')) {
        // SYNC-2: backfill missing, preserve existing
        const dst = path.join(tmplDst, e.name);
        if (await exists(dst)) skipped.push(dst);
        else { await copyFile(path.join(tmplSrc, e.name), dst, dryRun); added.push(dst); }
      } else {
        // other template files (e.g., rawdir-spec.md): preserve existing
        const dst = path.join(tmplDst, e.name);
        if (await exists(dst)) skipped.push(dst);
        else { await copyFile(path.join(tmplSrc, e.name), dst, dryRun); added.push(dst); }
      }
    }
  } else {
    warned.push('plugin doc/template/ not found — skipping templates sync');
  }

  // 4. scripts/* — backfill missing; preserve existing (SYNC-5)
  const scriptsSrc = path.join(pluginRoot, 'scripts');
  const scriptsDst = path.join(project, 'scripts');
  if (await exists(scriptsSrc)) {
    // ponytail: walk recursively; preserve existing files (don't overwrite user-modified scripts)
    await copyTreeBackfill(scriptsSrc, scriptsDst, dryRun, added, skipped);
  }

  // 5. schema/* — overwrite (SYNC-6)
  const schemaSrc = path.join(pluginRoot, 'doc', 'schema');
  const schemaDst = path.join(project, 'schema');
  if (await exists(schemaSrc)) {
    await overwriteTree(schemaSrc, schemaDst, dryRun, updated, skipped);
  }

  // 6. knowledge/index.md / overview.md / glossary.md — preserve (SYNC-7)
  // ponytail: no-op; build-skeleton.js created them, re-run preserves user edits.

  // 7. knowledge/log.md — handled by build-skeleton on first creation. Re-run preserves user content.

  return {
    project,
    dryRun,
    added,
    updated,
    skipped,
    warned,
    counts: {
      added: added.length,
      updated: updated.length,
      skipped: skipped.length,
      warned: warned.length,
    },
  };
}

async function copyTreeBackfill(srcRoot, dstRoot, dryRun, added, skipped) {
  const entries = await fs.readdir(srcRoot, { withFileTypes: true });
  for (const e of entries) {
    const src = path.join(srcRoot, e.name);
    const dst = path.join(dstRoot, e.name);
    if (e.isDirectory()) {
      if (!dryRun) await fs.mkdir(dst, { recursive: true });
      await copyTreeBackfill(src, dst, dryRun, added, skipped);
    } else {
      if (await exists(dst)) skipped.push(dst);
      else {
        if (!dryRun) {
          await fs.mkdir(path.dirname(dst), { recursive: true });
          await fs.copyFile(src, dst);
        }
        added.push(dst);
      }
    }
  }
}

async function overwriteTree(srcRoot, dstRoot, dryRun, updated, skipped) {
  const entries = await fs.readdir(srcRoot, { withFileTypes: true });
  if (!dryRun) await fs.mkdir(dstRoot, { recursive: true });
  for (const e of entries) {
    const src = path.join(srcRoot, e.name);
    const dst = path.join(dstRoot, e.name);
    if (e.isDirectory()) {
      await overwriteTree(src, dst, dryRun, updated, skipped);
    } else {
      // ponytail: overwrite. Track as updated.
      if (!dryRun) {
        await fs.mkdir(path.dirname(dst), { recursive: true });
        await fs.copyFile(src, dst);
      }
      updated.push(dst);
    }
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = await sync(args);
  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(2);
});
