#!/usr/bin/env node
/**
 * Stop hook — repo-level quality gates when Claude finishes responding.
 *
 * Quality-gate contract:
 *  1. Lint (ruff check) — issues channel (blocking)
 *  2. Format (ruff format --check) — issues channel (blocking)
 *  3. Type check (mypy) — issues channel (blocking)
 *  4. Tests + aggregate coverage — issues channel (blocking at 90%)
 *  5. Dependency audit (pip-audit) — advisory
 *  6. Documentation sync reminder
 *  7. Closure-evidence advisory (non-blocking) — issue #54
 *
 * Hardened (2026-08-02, venv-only policy 2026-08-12):
 *  - Gate tools resolve from project venvs ONLY (see utils VENV_ONLY_TOOLS):
 *    ruff/mypy may come from the gated tree's, the hook checkout's, or the
 *    main checkout's .venv; pytest must come from the gated tree's own .venv
 *    (any other venv would import a different tree via its editable install).
 *    PATH fallback for these tools is refused — a machine-global interpreter
 *    once masqueraded as a red repo gate.
 *  - Gates run once per GIT TREE that received testable edits — a session that
 *    edited files in a worktree gates that worktree (cwd = tree root), not the
 *    main checkout.
 *  - A missing tool is a BLOCKING issue with a fix hint, not a silent skip —
 *    a gate that cannot run must not report green.
 *  - pytest "no tests collected" (exit 5) is tolerated as a skip.
 *
 * IMPORTANT: Must check `stop_hook_active` to prevent infinite loops.
 * When Claude is already responding to a Stop hook block, this field is true.
 *
 * Exit codes:
 *   0 → Claude stops normally (stdout may contain JSON with decision)
 *   2 → Blocks the stop, stderr fed back to Claude
 */

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const {
  PROJECT_ROOT,
  readStdin,
  respondOk,
  respondBlock,
  loadSession,
  clearSession,
  detectService,
  expandWithDependents,
  findTreeRoot,
  mainRepoRootOf,
  isTestable,
  // Renamed on import (not aliased in utils itself): frees the bare
  // `runCommand` identifier for the closure-evidence probes' own local
  // helper below, which is byte-identical to the swinger/parent canon and
  // must not be reshaped to this file's richer gate-runner contract.
  runCommand: runGateCommand,
  formatCommandFailure
} = require('./utils');

// ──────────────────────────────────────────────
// Configuration (override via environment variables)
// ──────────────────────────────────────────────

const CONFIG = {
  runDependencyAudit: process.env.CLAUDE_HOOK_DEPENDENCY_AUDIT !== 'false',
  qualityTimeout: parseInt(process.env.CLAUDE_HOOK_QUALITY_TIMEOUT) || 300000,
  auditTimeout: parseInt(process.env.CLAUDE_HOOK_AUDIT_TIMEOUT) || 60000,
  runClosureCheck: process.env.CLAUDE_HOOK_CLOSURE_CHECK !== 'false',
};

// Cap applied to every runCommand() output/error string. Reused by the
// closure-evidence E1 probe below to detect when `git status` output was cut
// off mid-line, rather than silently under-reporting the dirty-file count.
const COMMAND_OUTPUT_CAP = 500;

// Shared timeout for the local-only git probes the closure-evidence advisory
// runs (resolveDefaultBranch / closureEvidenceForTree) — was a repeated magic
// number across every call site.
const GIT_PROBE_TIMEOUT_MS = 15000;

// ──────────────────────────────────────────────
// Dependency audit (pip-audit)
// ──────────────────────────────────────────────

function runDependencyAudit() {
  const result = runGateCommand(
    'Dependency audit (pip-audit)',
    'pip-audit',
    ['-r', 'requirements.txt'],
    { timeout: CONFIG.auditTimeout }
  );
  if (result.success) return { success: true };
  if (result.kind === 'unavailable') {
    return { success: true, note: 'pip-audit not installed, skipping vulnerability audit' };
  }
  return { success: false, output: result.output };
}

// ──────────────────────────────────────────────
// Git diff fallback detection
// ──────────────────────────────────────────────

/**
 * Use `git diff` to detect services with uncommitted changes.
 * Catches services missed by session tracking (e.g., changes made before
 * the session started, or files edited outside the hook-tracked flow).
 *
 * @returns {string[]} Service names with uncommitted changes
 */
function getGitDiffAffectedServices() {
  try {
    const result = runGateCommand(
      'Git diff detection',
      'git',
      ['diff', '--name-only', 'HEAD'],
      { timeout: 30000 }
    );
    if (!result.success || !result.output) return [];

    const files = result.output.split('\n').filter(Boolean);
    const services = new Set();
    for (const file of files) {
      const svc = detectService(file);
      if (svc) services.add(svc);
    }
    return [...services];
  } catch {
    return [];
  }
}

// ──────────────────────────────────────────────
// Skill reminders (docs-update, github-tracking)
// ──────────────────────────────────────────────

/**
 * Determine which skills should run before completing.
 *
 * Returns { mustRun: [...], optional: [...] }
 *  - mustRun: block the stop until these run (when there are doc/code changes)
 *  - optional: suggest but don't block
 */
function buildSkillReminders(session, editedFiles, affectedServices) {
  const mustRun = [];
  const optional = [];

  // Already reminded once — don't block again (prevents infinite loop)
  if (session.skillsReminded) {
    return { mustRun: [], optional: [] };
  }

  const hasCodeChanges = session.hasTestableChanges;
  const docsToUpdate = session.docsToUpdate || [];

  // /docs-update — when code changes touched contracts or architecture
  if (hasCodeChanges && docsToUpdate.length > 0) {
    const docNames = docsToUpdate.map(d =>
      d === 'contracts' ? 'CONTRACTS.md' : 'ARCHITECTURE.md'
    );
    mustRun.push(`/docs-update — update ${docNames.join(', ')} to reflect code changes`);
  }

  // /github-tracking — when there were meaningful code changes in services
  if (hasCodeChanges && affectedServices.length > 0) {
    mustRun.push(
      `/github-tracking — log progress for services: ${affectedServices.join(', ')}`
    );
  }

  return { mustRun, optional };
}

// ──────────────────────────────────────────────
// Gate tree roots
// ──────────────────────────────────────────────

/**
 * The git trees whose gates must run: every distinct tree root that received a
 * testable edit this session (a worktree gates itself, with cwd = the worktree
 * root), falling back to the project root.
 */
function gateTreeRoots(editedFiles) {
  const roots = new Set();
  for (const f of editedFiles) {
    if (!isTestable(f)) continue;
    const root = findTreeRoot(f);
    if (root) roots.add(root);
  }
  if (roots.size === 0) roots.add(PROJECT_ROOT);
  return [...roots];
}

// ──────────────────────────────────────────────
// Closure-evidence advisory (loud, never blocks) — issue #54
// ──────────────────────────────────────────────
//
// The workspace SDLC mandates a closure phase (review, e2e, regression,
// tracking, docs, worktree housekeeping) that sessions can silently skip.
// This advisory surfaces the skip mechanically: it never changes the exit
// code, never writes to stderr, and disappears once the evidence is clean.

/**
 * A minimal execFileSync-based command runner for the closure-evidence git
 * probes only — deliberately separate from `runGateCommand` (this file's
 * richer, venv-aware gate runner imported from utils). The probes are
 * local-only git plumbing; they don't need venv resolution, `.cmd` wrapping,
 * or the gate-runner's result shape. Ported verbatim from the swinger/parent
 * canon so the closure block's behavior stays byte-identical across harnesses.
 */
function runCommand(file, args, opts = {}) {
  const timeout = opts.timeout || CONFIG.qualityTimeout;
  const cwd = opts.cwd || PROJECT_ROOT;
  if (!fs.existsSync(cwd)) return { success: false, status: null, code: null, output: '', error: `cwd missing: ${cwd}` };
  try {
    const output = execFileSync(file, args, { cwd, stdio: 'pipe', timeout, encoding: 'utf8', windowsHide: true });
    return { success: true, status: 0, code: null, output: (output || '').substring(0, COMMAND_OUTPUT_CAP) };
  } catch (e) {
    return {
      success: false,
      status: typeof e.status === 'number' ? e.status : null,
      code: e.code || null, // 'ENOENT' when the tool binary is missing
      error: (e.message || '').substring(0, 300),
      output: ((e.stdout || '') + (e.stderr || '')).substring(0, COMMAND_OUTPUT_CAP),
    };
  }
}

/**
 * E2 default-branch resolution: origin/HEAD → main → master → null (skip E2).
 * Local refs only — never touches the network.
 */
function resolveDefaultBranch(treeRoot) {
  const originHead = runCommand('git', ['symbolic-ref', '--short', 'refs/remotes/origin/HEAD'], { cwd: treeRoot, timeout: GIT_PROBE_TIMEOUT_MS });
  if (originHead.success && originHead.output.trim()) {
    const branch = originHead.output.trim().replace(/^origin\//, '');
    // origin/HEAD can name a branch whose local ref was never created (e.g. a
    // sparse/shallow clone) — verify it locally before trusting it, mirroring
    // the fallback loop below, so a missing local default explicitly skips E2
    // instead of feeding rev-list a ref that silently fails.
    const verify = runCommand('git', ['show-ref', '--verify', '--quiet', `refs/heads/${branch}`], { cwd: treeRoot, timeout: GIT_PROBE_TIMEOUT_MS });
    if (verify.success) return branch;
  }
  for (const candidate of ['main', 'master']) {
    const verify = runCommand('git', ['show-ref', '--verify', '--quiet', `refs/heads/${candidate}`], { cwd: treeRoot, timeout: GIT_PROBE_TIMEOUT_MS });
    if (verify.success) return candidate;
  }
  return null;
}

/**
 * E1 (uncommitted tracked changes) + E2 (branch ahead of default) for one
 * git tree. Each probe is independently fail-open: a git error just means
 * that probe reports nothing, the other still can.
 */
function closureEvidenceForTree(treeRoot, treeLabel) {
  const lines = [];

  try {
    const status = runCommand('git', ['status', '--porcelain', '--untracked-files=no'], { cwd: treeRoot, timeout: GIT_PROBE_TIMEOUT_MS });
    if (status.success && status.output.trim()) {
      // Split the UNTRIMMED output — porcelain lines start with a leading
      // status char that a whole-string .trim() would otherwise eat.
      let files = status.output.split('\n').filter(l => l.length > 0).map(l => l.slice(3).trim());
      // runCommand caps output at COMMAND_OUTPUT_CAP chars: past that, the
      // last line can be a mid-line cut (a garbled filename) and the count
      // would silently under-report. Drop the possibly-truncated last entry
      // and mark the count as a lower bound instead.
      const truncated = status.output.length >= COMMAND_OUTPUT_CAP;
      if (truncated) files = files.slice(0, -1);
      const shown = files.slice(0, 5).join(', ') + (files.length > 5 ? ', ...' : '');
      const count = truncated ? `${files.length}+` : `${files.length}`;
      lines.push(`  - [${treeLabel}] uncommitted tracked changes: ${count} file(s) (${shown})`);
    }
  } catch { /* fail-open: skip E1 */ }

  try {
    const current = runCommand('git', ['rev-parse', '--abbrev-ref', 'HEAD'], { cwd: treeRoot, timeout: GIT_PROBE_TIMEOUT_MS });
    const branch = current.success ? current.output.trim() : '';
    if (branch && branch !== 'HEAD') {
      const defaultBranch = resolveDefaultBranch(treeRoot);
      if (defaultBranch && branch !== defaultBranch) {
        const ahead = runCommand('git', ['rev-list', '--count', `${defaultBranch}..HEAD`], { cwd: treeRoot, timeout: GIT_PROBE_TIMEOUT_MS });
        const count = ahead.success ? parseInt(ahead.output.trim(), 10) : 0;
        if (count > 0) {
          lines.push(`  - [${treeLabel}] branch '${branch}' is ${count} commit(s) ahead of '${defaultBranch}' (PR not merged)`);
        }
      }
    }
  } catch { /* fail-open: skip E2 */ }

  return lines;
}

/**
 * E3 — leftover `.claude/worktrees/*` under each tree's MAIN checkout
 * (resolved via mainRepoRootOf), deduped so several tree roots that share a
 * main checkout are only reported once.
 */
function closureWorktreeEvidence(treeRoots) {
  const lines = [];
  const seenMainRepos = new Set();
  for (const treeRoot of treeRoots) {
    try {
      const mainRepo = mainRepoRootOf(treeRoot) || treeRoot;
      if (seenMainRepos.has(mainRepo)) continue;
      seenMainRepos.add(mainRepo);
      const wtDir = path.join(mainRepo, '.claude', 'worktrees');
      if (!fs.existsSync(wtDir)) continue;
      const names = fs.readdirSync(wtDir, { withFileTypes: true })
        .filter(e => e.isDirectory())
        .map(e => e.name);
      if (names.length > 0) {
        lines.push(`  - [${path.basename(mainRepo)}] leftover worktree(s) under .claude/worktrees/: ${names.join(', ')}`);
      }
    } catch { /* fail-open: skip this tree's E3 */ }
  }
  return lines;
}

function formatClosureBlock(evidenceLines) {
  return [
    '=================== CLOSURE PENDING ===================',
    'Code was edited this session, but the tree still shows open work:',
    ...evidenceLines,
    'Closure checklist (SDLC closure phase - agents/rules/_shared-workflow.md):',
    '  [ ] Code review (REVIEWER) done',
    '  [ ] Live e2e of the changed surface',
    '  [ ] Tiered regression run (T1 minimum)',
    '  [ ] github-tracking: issue DoD updated',
    '  [ ] docs-update + spec archived',
    '  [ ] Worktree housekeeping: PR merged, branch deleted, worktree removed',
    'Advisory only - this does NOT block the stop.',
    '========================================================',
  ].join('\n');
}

/**
 * Builds the CLOSURE PENDING advisory (empty string = clean / not applicable).
 * Fires only when repo-owned code was edited this session — the exact
 * predicate the hook already uses (in main()) to decide whether to run gates
 * at all: `session.hasTestableChanges || mergedServices.length > 0`. Never
 * throws (NFR-2 — try/caught to '', on top of each probe's own fail-open
 * handling).
 */
function buildClosureAdvisory(editedFiles, session, ownedAffected) {
  try {
    if (!(session.hasTestableChanges || ownedAffected.length > 0)) return '';

    const treeRoots = gateTreeRoots(editedFiles);
    // 'project' (not a harness-specific literal) so a stamped copy of this
    // hook in another harness never prints algo_beta's name as its fallback.
    const name = ownedAffected.length ? ownedAffected.join(', ') : 'project';

    const evidenceLines = [];
    for (const treeRoot of treeRoots) {
      const treeLabel = treeRoot === PROJECT_ROOT ? name : `${name} @ ${treeRoot}`;
      evidenceLines.push(...closureEvidenceForTree(treeRoot, treeLabel));
    }
    evidenceLines.push(...closureWorktreeEvidence(treeRoots));

    if (evidenceLines.length === 0) return '';
    return formatClosureBlock(evidenceLines);
  } catch {
    return '';
  }
}

// ──────────────────────────────────────────────
// Main
// ──────────────────────────────────────────────

async function main() {
  try {
    const input = await readStdin();

    // CRITICAL: Prevent infinite loops.
    // When Claude is already responding to a previous Stop hook block,
    // stop_hook_active is true. We must exit 0 immediately.
    if (input.stop_hook_active) {
      respondOk({});
      return;
    }

    const session = loadSession();
    const sessionServices = session.affectedServices || [];
    const editedFiles = session.editedFiles || [];

    // Merge session-tracked services with git diff detection (catches missed services)
    const gitDiffServices = getGitDiffAffectedServices();
    const mergedServices = [...new Set([...sessionServices, ...gitDiffServices])];

    // Expand with dependent services (e.g., editing core → also test fincli)
    const affectedServices = expandWithDependents(mergedServices);

    // Clean up the rules-loaded state so the next conversation starts fresh
    try {
      const rulesStateFile = path.join(__dirname, '.rules-loaded');
      if (require('fs').existsSync(rulesStateFile)) {
        require('fs').unlinkSync(rulesStateFile);
      }
    } catch { /* best effort */ }

    // Nothing edited — nothing to check
    if (editedFiles.length === 0 && gitDiffServices.length === 0) {
      clearSession();
      respondOk({});
      return;
    }

    // Only non-code edits — skip quality gates
    if (!session.hasTestableChanges && gitDiffServices.length === 0) {
      clearSession();
      respondOk({
        systemMessage: `Session: ${editedFiles.length} files edited (no testable code changes).`
      });
      return;
    }

    // ── Run repo-level quality gates ──
    const failures = [];
    const warnings = [];
    const skipped = [];

    const qualityChecks = [
      {
        name: 'Lint (ruff)',
        command: 'ruff',
        args: ['check', '.'],
      },
      {
        name: 'Format (ruff format --check)',
        command: 'ruff',
        args: ['format', '--check', '.'],
      },
      {
        name: 'Strict mypy',
        command: 'mypy',
        args: [],
      },
      {
        name: 'Tests and aggregate coverage',
        command: 'pytest',
        args: ['tests/', '--cov', '--cov-report=term-missing'],
      },
    ];

    // Run the gates once per git tree that received testable edits, with
    // cwd = that tree's root (a worktree session gates the worktree, not the
    // main checkout). Tools resolve from the gated tree's venv (see utils).
    const treeRoots = gateTreeRoots(editedFiles);
    for (const treeRoot of treeRoots) {
      const treeLabel = treeRoot === PROJECT_ROOT ? '' : `tree: ${treeRoot}\n`;
      for (const check of qualityChecks) {
        const result = runGateCommand(
          check.name,
          check.command,
          check.args,
          { timeout: CONFIG.qualityTimeout, cwd: treeRoot }
        );
        if (result.success) continue;
        if (check.command === 'pytest' && result.status === 5) {
          skipped.push({ name: check.name, reason: 'no tests collected' });
          continue;
        }
        if (result.kind === 'unavailable' && !/PATH fallback is refused/.test(result.output || '')) {
          // A gate that cannot run must not report green — append a fix hint
          // to failures that did not come from the venv-only resolver (spawn
          // errors on a corrupt venv launcher, etc.). Resolver refusals
          // already carry the full diagnostic, detected by its marker text.
          result.output =
            (result.output ? `${result.output}\n` : '') +
            `tool '${check.command}' could not run — create the gated tree's venv: ` +
            'python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]" ' +
            '(.venv/bin/python on POSIX)';
        }
        if (treeLabel) result.output = treeLabel + (result.output || '');
        failures.push(result);
      }
    }

    // Dependency audit (once, repo-level)
    let auditResult = null;
    if (CONFIG.runDependencyAudit) {
      auditResult = runDependencyAudit();
      if (auditResult.note && /not installed/i.test(auditResult.note)) {
        skipped.push({ name: 'Dependency audit (pip-audit)', reason: auditResult.note });
      } else if (!auditResult.success) {
        warnings.push({
          name: 'Dependency audit (pip-audit)',
          output: (auditResult.output || '').substring(0, 300)
        });
      }
    }

    // Documentation reminder
    const docsToUpdate = session.docsToUpdate || [];
    const docsReminder = docsToUpdate.map(d =>
      d === 'contracts' ? 'CONTRACTS.md' : 'ARCHITECTURE.md'
    );

    // ── Skill reminders (docs-update, github-tracking) ──
    const skillReminders = buildSkillReminders(session, editedFiles, affectedServices);

    // ── Normal completion ──
    clearSession();

    // Computed here (before the pass/fail fork) so it rides along on the
    // eventual green stop only — gate failures block via respondBlock below
    // and never see this text (advisory text must never muddy blocking
    // feedback Claude has to act on).
    const closureAdvisory = CONFIG.runClosureCheck
      ? buildClosureAdvisory(editedFiles, session, mergedServices)
      : '';

    if (failures.length > 0) {
      const failureMessage = failures.map(formatCommandFailure).join('\n\n');
      respondBlock(`Required quality gates failed:\n\n${failureMessage}\n`);
      return;
    }

    let message = '';
    const servicesLabel = affectedServices.length > 0 ? affectedServices.join(', ') : 'repo';
    message = `All required quality gates passed for: ${servicesLabel}`;
    if (warnings.length > 0) {
      const warnLines = warnings.map(w => `  - ${w.name}`).join('\n');
      message += `\nWarnings (advisory):\n${warnLines}`;
    }
    if (skipped.length > 0) {
      const skipLines = skipped.map(s => `  - ${s.name}: ${s.reason}`).join('\n');
      message += `\nSkipped:\n${skipLines}`;
    }
    if (docsReminder.length > 0) message += `\nDocs reminder: update ${docsReminder.join(', ')}`;
    if (skillReminders.mustRun.length > 0) {
      message += `\nSkills to run: ${skillReminders.mustRun.join('; ')}`;
    }
    if (skillReminders.optional.length > 0) {
      message += `\nOptional skills: ${skillReminders.optional.join(', ')}`;
    }
    if (closureAdvisory) message += '\n\n' + closureAdvisory;

    respondOk({ systemMessage: message });

  } catch (error) {
    clearSession();
    respondBlock(`on-stop hook infrastructure failure: ${error.message}\n`);
  }
}


// A hook infrastructure failure must not produce a false-green Stop result.
main().catch((error) => {
  try { clearSession(); } catch { /* ignore */ }
  respondBlock(`on-stop hook infrastructure failure: ${error.message}\n`);
});
