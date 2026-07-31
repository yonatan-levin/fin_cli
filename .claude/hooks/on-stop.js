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
 * IMPORTANT: Must check `stop_hook_active` to prevent infinite loops.
 * When Claude is already responding to a Stop hook block, this field is true.
 *
 * Exit codes:
 *   0 → Claude stops normally (stdout may contain JSON with decision)
 *   2 → Blocks the stop, stderr fed back to Claude
 */

const { execSync } = require('child_process');
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
  try {
    execSync('pip-audit -r requirements.txt', {
      cwd: PROJECT_ROOT,
      stdio: 'pipe',
      timeout: CONFIG.auditTimeout,
      windowsHide: true,
      shell: process.platform === 'win32' ? process.env.COMSPEC || 'cmd.exe' : true
    });
    return { success: true };
  } catch (e) {
    if (e.code === 'ENOENT' || /not found|No such file/i.test(e.message)) {
      return { success: true, note: 'pip-audit not installed, skipping vulnerability audit' };
    }
    return {
      success: false,
      output: (e.stdout?.toString() || '') + (e.stderr?.toString() || '') || e.message
    };
  }
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

    for (const check of qualityChecks) {
      const result = runCommand(
        check.name,
        check.command,
        check.args,
        { timeout: CONFIG.qualityTimeout }
      );
      if (!result.success) {
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
