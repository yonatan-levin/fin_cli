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
 *
 * Hardened (2026-08-02):
 *  - Gate tools resolve from the gated tree's .venv (falling back to the main
 *    checkout's venv, then PATH) — hooks inherit a PATH without ruff/mypy/pytest.
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

const path = require('path');
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
  isTestable,
  runCommand,
  formatCommandFailure
} = require('./utils');

// ──────────────────────────────────────────────
// Configuration (override via environment variables)
// ──────────────────────────────────────────────

const CONFIG = {
  runDependencyAudit: process.env.CLAUDE_HOOK_DEPENDENCY_AUDIT !== 'false',
  qualityTimeout: parseInt(process.env.CLAUDE_HOOK_QUALITY_TIMEOUT) || 300000,
  auditTimeout: parseInt(process.env.CLAUDE_HOOK_AUDIT_TIMEOUT) || 60000,
};

// ──────────────────────────────────────────────
// Dependency audit (pip-audit)
// ──────────────────────────────────────────────

function runDependencyAudit() {
  const result = runCommand(
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
    const result = runCommand(
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
        const result = runCommand(
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
        if (result.kind === 'unavailable') {
          // A gate that cannot run must not report green — block with a fix hint.
          result.output =
            `tool '${check.command}' not found (checked ${treeRoot}/.venv and PATH) ` +
            `— create the venv / pip install -e ".[dev]"` +
            (result.output ? `\n${result.output}` : '');
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
