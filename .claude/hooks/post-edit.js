#!/usr/bin/env node
/**
 * PostToolUse hook for Edit|Write tools — quality checks after file edits.
 *
 * Runs lightweight, per-file checks immediately after each edit:
 *  - Tracks edited files and affected services in a session file
 *  - Scans for accidentally committed secrets
 *  - Runs OWASP security pattern checks on auth/security files
 *  - Runs ruff check --fix + ruff format + mypy on Python files
 *  - Flags when documentation may need updating
 *
 * PostToolUse hooks CANNOT block (the tool already executed).
 * We use `systemMessage` to surface warnings in the conversation.
 *
 * Exit codes:
 *   0 → success (stdout parsed for JSON)
 *   other → non-blocking error (stderr shown in verbose mode)
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const {
  PROJECT_ROOT,
  readStdin,
  respondOk,
  trackEdit,
  detectService,
  isSecurityFile,
  getDocUpdateNeeded,
  NON_TESTABLE_EXTENSIONS
} = require('./utils');

// ──────────────────────────────────────────────
// Secret detection
// ──────────────────────────────────────────────

const SECRET_PATTERNS = [
  { re: /api[_-]?key\s*[:=]\s*['"][^'"]{8,}['"]/gi, label: 'API key assignment' },
  { re: /secret[_-]?key\s*[:=]\s*['"][^'"]{8,}['"]/gi, label: 'Secret key assignment' },
  { re: /password\s*[:=]\s*['"][^'"]{4,}['"]/gi, label: 'Hardcoded password' },
  { re: /private[_-]?key\s*[:=]\s*['"][^'"]{8,}['"]/gi, label: 'Private key assignment' },
  { re: /-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----/, label: 'Embedded private key' },
  { re: /sk-[a-zA-Z0-9]{20,}/, label: 'OpenAI API key' },
  { re: /ghp_[a-zA-Z0-9]{36,}/, label: 'GitHub personal access token' },
  { re: /xox[bpras]-[a-zA-Z0-9-]{10,}/, label: 'Slack token' },
];

function checkForSecrets(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const issues = [];
    for (const { re, label } of SECRET_PATTERNS) {
      // Reset lastIndex for global patterns
      re.lastIndex = 0;
      if (re.test(content)) {
        issues.push(label);
      }
    }
    return issues;
  } catch {
    return [];
  }
}

// ──────────────────────────────────────────────
// OWASP security checks
// ──────────────────────────────────────────────

const OWASP_PATTERNS = [
  // A1: Injection
  { re: /\$\{.*\}.*query|query.*\$\{/gi, issue: 'Possible SQL injection via template literal in query' },
  { re: /eval\s*\(/gi, issue: 'eval() usage — potential code injection' },
  { re: /new\s+Function\s*\(/gi, issue: 'Dynamic Function() — potential code injection' },
  // A2: Broken Authentication
  { re: /expiresIn.*['"]?\d{1,2}s['"]?/gi, issue: 'Very short token expiration' },
  // A3: Sensitive Data Exposure
  { re: /console\.(log|info|debug)\s*\(.*password/gi, issue: 'Password logged to console' },
  { re: /console\.(log|info|debug)\s*\(.*token/gi, issue: 'Token logged to console' },
  { re: /console\.(log|info|debug)\s*\(.*secret/gi, issue: 'Secret logged to console' },
  // A5: Broken Access Control
  { re: /@Public\(\)/gi, issue: '@Public() decorator — verify this is intentional' },
  // A6: Security Misconfiguration
  { re: /cors.*origin.*\*/gi, issue: 'CORS allows all origins (*)' },
  // A7: XSS
  { re: /innerHTML\s*=/gi, issue: 'innerHTML assignment — potential XSS' },
  { re: /dangerouslySetInnerHTML/gi, issue: 'dangerouslySetInnerHTML — verify input is sanitized' },
];

function runSecurityChecks(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const issues = [];
    for (const { re, issue } of OWASP_PATTERNS) {
      re.lastIndex = 0;
      if (re.test(content)) issues.push(issue);
    }
    return issues;
  } catch {
    return [];
  }
}

// ──────────────────────────────────────────────
// Lint fix (ruff + mypy for Python files)
// ──────────────────────────────────────────────

function runLintFix(filePath) {
  try {
    const ext = path.extname(filePath).toLowerCase();

    // Python files: ruff check --fix, ruff format, mypy (advisory in Phase 1)
    if (ext === '.py') {
      try {
        execSync(`ruff check --fix "${filePath}"`, { stdio: 'pipe', timeout: 30000, cwd: PROJECT_ROOT });
      } catch {
        // swallow advisory output — ruff exits non-zero if findings remain after fix
      }
      try {
        execSync(`ruff format "${filePath}"`, { stdio: 'pipe', timeout: 15000, cwd: PROJECT_ROOT });
      } catch {
        // swallow advisory output — formatting failure is rare; don't block
      }
      try {
        execSync(`mypy "${filePath}"`, { stdio: 'pipe', timeout: 30000, cwd: PROJECT_ROOT });
      } catch {
        // swallow advisory output — mypy errors are advisory in Phase 1
      }
      return { success: true };
    }

    // Non-Python files: skip lint fix
    return { success: true };
  } catch (e) {
    return { success: false, error: (e.message || '').substring(0, 200) };
  }
}

// ──────────────────────────────────────────────
// Main
// ──────────────────────────────────────────────

async function main() {
  try {
    const input = await readStdin();
    const filePath = (input.tool_input && input.tool_input.file_path) || '';

    if (!filePath) {
      respondOk({});
      return;
    }

    // Track this edit in session
    const session = trackEdit(filePath);

    const ext = path.extname(filePath).toLowerCase();

    // Skip non-code files
    if (NON_TESTABLE_EXTENSIONS.includes(ext)) {
      respondOk({ suppressOutput: true });
      return;
    }

    const warnings = [];
    const service = detectService(filePath);

    // 1. Secret scan (always run on code files)
    const secretIssues = checkForSecrets(filePath);
    if (secretIssues.length > 0) {
      warnings.push(`SECRETS WARNING in ${path.basename(filePath)}: ${secretIssues.join(', ')}`);
    }

    // 2. OWASP checks on security-related files
    if (isSecurityFile(filePath)) {
      const secIssues = runSecurityChecks(filePath);
      if (secIssues.length > 0) {
        warnings.push(`SECURITY in ${path.basename(filePath)}: ${secIssues.join('; ')}`);
      }
    }

    // 3. Lint auto-fix: ruff + mypy for Python files
    if (['.py'].includes(ext)) {
      runLintFix(filePath);
    }

    // 4. Documentation update reminder
    const docUpdates = getDocUpdateNeeded(filePath);
    if (docUpdates.length > 0) {
      const docNames = docUpdates.map(d =>
        d === 'contracts' ? 'CONTRACTS.md' : 'ARCHITECTURE.md'
      );
      warnings.push(`Consider updating: ${docNames.join(', ')}`);
    }

    // Build response
    const response = { suppressOutput: true };

    // Surface warnings via systemMessage so they appear in the conversation
    if (warnings.length > 0) {
      response.suppressOutput = false;
      response.systemMessage = warnings.join('\n');
    }

    respondOk(response);

  } catch (error) {
    process.stderr.write(`post-edit hook error: ${error.message}\n`);
    process.exit(1);
  }
}

main();
