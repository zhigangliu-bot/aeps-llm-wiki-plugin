#!/usr/bin/env node
/**
 * detect-state.js - Detect init state of a project directory.
 *
 * Detects whether {project}/ has all 6 top-level directories with their .gitkeep files.
 * Returns JSON: { state: "fresh"|"reentry", missing: [...], present: [...] }
 *
 * Usage:
 *   node scripts/init/detect-state.js --project <dir> [--json]
 *
 * Exit codes:
 *   0 - success
 *   1 - invalid args
 *   2 - project dir does not exist
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';

const TOP_DIRS = ['inbox', 'raw', 'scripts', 'templates', 'schema', 'knowledge'];
const GITKEEP = '.gitkeep';

function parseArgs(argv) {
  const args = { project: null, json: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--project') args.project = argv[++i];
    else if (a === '--json') args.json = true;
    else if (a === '-h' || a === '--help') {
      console.log('Usage: node detect-state.js --project <dir> [--json]');
      process.exit(0);
    }
  }
  return args;
}

async function exists(p) {
  try { await fs.access(p); return true; } catch { return false; }
}

async function detect(project) {
  const projectAbs = path.resolve(project);
  if (!(await exists(projectAbs))) {
    return { state: 'fresh', missing: [...TOP_DIRS], present: [], error: 'project_dir_not_found', project: projectAbs };
  }
  const stat = await fs.stat(projectAbs);
  if (!stat.isDirectory()) {
    return { state: 'fresh', missing: [...TOP_DIRS], present: [], error: 'not_a_directory', project: projectAbs };
  }
  const missing = [];
  const present = [];
  for (const d of TOP_DIRS) {
    const dirAbs = path.join(projectAbs, d);
    const keep = path.join(dirAbs, GITKEEP);
    if ((await exists(dirAbs)) && (await exists(keep))) {
      present.push(d);
    } else {
      missing.push(d);
    }
  }
  // ponytail: reentry only if all 6 top dirs have .gitkeep; otherwise fresh
  const state = missing.length === 0 ? 'reentry' : 'fresh';
  return { state, missing, present, project: projectAbs };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.project) {
    console.error('Error: --project <dir> is required');
    process.exit(1);
  }
  const result = await detect(args.project);
  // ponytail: always emit structured JSON to stdout
  console.log(JSON.stringify(result));
  // exit 0 even on "fresh" — it's a valid state. error cases carry error field but exit 0.
  process.exit(0);
}

main().catch(err => {
  console.error(JSON.stringify({ error: 'unexpected', message: err.message }));
  process.exit(1);
});
