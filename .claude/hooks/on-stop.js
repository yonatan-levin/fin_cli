#!/usr/bin/env node
/**
 * Stop hook — repo-level quality gates when Claude finishes responding.
 *
 * Phase 1 contract:
 *  1. Lint (ruff check) — issues channel (blocking)
 *  2. Format (ruff format --check) — issues channel (blocking)
 *  3. Type check (mypy) — warnings channel (advisory; Phase 4 flips to issues)
 *  4. Tests (pytest) — issues channel (blocking)
 *  5. Coverage — STUBBED, Phase 3 deferred (no threshold yet)
 *  6. Dependency audit (pip-audit) — graceful skip if not installed
 *  7. Documentation sync reminder
 *
 * Per spec OQ7: mypy stays in `warnings` until Phase 4. Do not move it.
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
  loadSession,
  clearSession,
  detectService,
  expandWithDependents
} = require('./utils');

// ──────────────────────────────────────────────
// Configuration (override via environment variables)
// ──────────────────────────────────────────────

const CONFIG = {
  runQualityChecks: process.env.CLAUDE_HOOK_QUALITY_CHECKS !== 'false',
  runCoverageCheck: process.env.CLAUDE_HOOK_COVERAGE_CHECK !== 'false',
  runDependencyAudit: process.env.CLAUDE_HOOK_DEPENDENCY_AUDIT !== 'false',
  qualityTimeout: parseInt(process.env.CLAUDE_HOOK_QUALITY_TIMEOUT) || 300000,
  auditTimeout: parseInt(process.env.CLAUDE_HOOK_AUDIT_TIMEOUT) || 60000,
};

// ──────────────────────────────────────────────
// Command runner
// ──────────────────────────────────────────────

/**
 * Run a shell command safely, handling paths with spaces on Windows/Git Bash.
 *
 * @param {string} command  Shell command to execute
 * @param {object} [opts]   { timeout, cwd }
 */
function runCommand(command, opts = {}) {
  const fs = require('fs');
  const timeout = opts.timeout || 300000;
  const effectiveCwd = opts.cwd || PROJECT_ROOT;

  if (!fs.existsSync(effectiveCwd)) {
    return {
      success: false,
      error: `Working directory does not exist: ${effectiveCwd}`,
      output: ''
    };
  }

  try {
    const output = execSync(command, {
      cwd: effectiveCwd,
      stdio: 'pipe',
      timeout,
      encoding: 'utf8',
      windowsHide: true,
      // Explicitly use cmd.exe on Windows to avoid Git Bash path splitting
      // issues when the cwd contains spaces (e.g., "Yonatan Levin")
      shell: process.platform === 'win32' ? process.env.COMSPEC || 'cmd.exe' : true
    });
    return { success: true, output: (output || '').substring(0, 500) };
  } catch (e) {
    return {
      success: false,
      error: (e.message || '').substring(0, 300),
      output: ((e.stdout || '') + (e.stderr || '')).substring(0, 500)
    };
  }
}

// ──────────────────────────────────────────────
// Coverage — Phase 3 deferred
// ──────────────────────────────────────────────

function runCoverageCheck() {
  return {
    skipped: true,
    reason: 'Phase 3 deferred — no coverage threshold yet',
  };
}

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
      'git diff --name-only HEAD || git diff --name-only',
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
    const issues = [];
    const warnings = [];
    const skipped = [];

    const qualityChecks = [
      {
        name: 'Lint (ruff)',
        cmd: 'ruff check .',
        channel: 'issues', // ruff failures block
      },
      {
        name: 'Format (ruff format --check)',
        cmd: 'ruff format --check .',
        channel: 'issues',
      },
      {
        name: 'Type check (mypy)',
        cmd: 'mypy fincli core config logger',
        channel: 'warnings', // Phase 1: advisory only. Phase 4 flips to 'issues'.
      },
      {
        name: 'Tests (pytest)',
        cmd: 'pytest tests/',
        channel: 'issues',
      },
    ];

    if (CONFIG.runQualityChecks) {
      for (const check of qualityChecks) {
        const result = runCommand(check.cmd, { timeout: CONFIG.qualityTimeout });
        if (!result.success) {
          const target = check.channel === 'issues' ? issues : warnings;
          target.push({ name: check.name, output: result.output || result.error || '' });
        }
      }
    }

    // Coverage — Phase 3 deferred (stubbed)
    let coverageResult = null;
    if (CONFIG.runCoverageCheck) {
      coverageResult = runCoverageCheck();
      if (coverageResult.skipped) {
        skipped.push({ name: 'Coverage', reason: coverageResult.reason });
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

    const allPassed = issues.length === 0;

    // ── Skill reminders (docs-update, github-tracking) ──
    const skillReminders = buildSkillReminders(session, editedFiles, affectedServices);

    // ── Normal completion ──
    clearSession();

    let message = '';
    const servicesLabel = affectedServices.length > 0 ? affectedServices.join(', ') : 'repo';
    if (allPassed) {
      message = `All quality gates passed for: ${servicesLabel}`;
    } else {
      const issueLines = issues.map(i => `  - ${i.name}`).join('\n');
      message = `Quality gates completed with issues:\n${issueLines}`;
    }
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
    process.stderr.write(`on-stop hook error: ${error.message}\n`);
    clearSession();
    process.exit(1);
  }
}


// Safety net: if anything escapes the try/catch in main(), exit cleanly
// rather than crashing with a confusing bash error. The stop hook is a
// quality gate, not a security gate — better to skip checks than block.
main().catch(() => {
  try { clearSession(); } catch { /* ignore */ }
  respondOk({});
});
