#!/usr/bin/env node
/**
 * sync-report.js - Aggregate sync results from prior init phase into a human-readable summary.
 *
 * Reads JSON output of build-skeleton / sync-files / patch-claude-md via stdin
 * (one JSON per line) and produces a single summary.
 *
 * Usage:
 *   node scripts/init/sync-report.js --project <dir> [--json]
 *   # OR pipe JSON lines via stdin:
 *   cat results.jsonl | node scripts/init/sync-report.js --project <dir>
 *
 * Exit codes: 0 ok
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

function parseArgs(argv) {
  const args = { project: null, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--json') args.json = true;
  }
  if (!args.project) {
    console.error('Error: --project <dir> is required');
    process.exit(1);
  }
  return args;
}

async function readStdin() {
  // ponytail: read all stdin (assumed small — sync outputs only)
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

async function report(args) {
  const project = path.resolve(args.project);
  const stdinData = await readStdin().catch(() => '');
  const lines = stdinData.split(/\r?\n/).filter(Boolean);
  const phases = [];
  for (const line of lines) {
    try {
      phases.push(JSON.parse(line));
    } catch {
      // ignore non-JSON lines
    }
  }

  // ponytail: aggregate counts across phases
  let addedCount = 0, updatedCount = 0, skippedCount = 0, warnedCount = 0;
  const allAdded = [];
  const allUpdated = [];
  const allSkipped = [];
  const allWarned = [];
  for (const p of phases) {
    if (Array.isArray(p.added)) { allAdded.push(...p.added); addedCount += p.added.length; }
    if (Array.isArray(p.updated)) { allUpdated.push(...p.updated); updatedCount += p.updated.length; }
    if (Array.isArray(p.skipped)) { allSkipped.push(...p.skipped); skippedCount += p.skipped.length; }
    if (Array.isArray(p.warned)) { allWarned.push(...p.warned); warnedCount += p.warned.length; }
  }

  const summary = {
    project,
    phases: phases.length,
    counts: { added: addedCount, updated: updatedCount, skipped: skippedCount, warned: warnedCount },
    added: allAdded,
    updated: allUpdated,
    skipped: allSkipped,
    warned: allWarned,
    status: 'init_complete',
  };

  if (args.json) {
    console.log(JSON.stringify(summary, null, 2));
    return;
  }

  // ponytail: human-readable report
  const lines2 = [];
  lines2.push('=== init sync summary ===');
  lines2.push(`project: ${project}`);
  lines2.push(`phases: ${phases.length}`);
  lines2.push(`added:   ${addedCount}`);
  lines2.push(`updated: ${updatedCount}`);
  lines2.push(`skipped: ${skippedCount}`);
  lines2.push(`warned:  ${warnedCount}`);
  if (allAdded.length) {
    lines2.push('\n--- added files ---');
    for (const f of allAdded) lines2.push('+ ' + f);
  }
  if (allUpdated.length) {
    lines2.push('\n--- updated files ---');
    for (const f of allUpdated) lines2.push('~ ' + f);
  }
  if (allSkipped.length > 0 && allSkipped.length <= 50) {
    lines2.push('\n--- skipped (preserved) ---');
    for (const f of allSkipped) lines2.push('  ' + f);
  } else if (allSkipped.length > 50) {
    lines2.push(`\n--- skipped (${allSkipped.length} total, omitted for brevity) ---`);
  }
  if (allWarned.length) {
    lines2.push('\n--- warnings ---');
    for (const w of allWarned) lines2.push('! ' + w);
  }
  lines2.push('\n=== init complete ===');
  console.log(lines2.join('\n'));
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  await report(args);
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(1);
});
