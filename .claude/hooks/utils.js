#!/usr/bin/env node
/**
 * Shared utilities for Claude Code hooks — algo_beta Fin CLI (Python)
 *
 * Provides context-aware detection of modules, testability checks,
 * session tracking, and proper Claude Code response formatting.
 *
 * Claude Code hooks receive JSON on stdin and communicate via:
 * - exit 0 + stdout JSON → success (action proceeds)
 * - exit 2 + stderr      → blocking error (action blocked)
 * - other exit codes      → non-blocking error (action proceeds)
 */

const fs = require('fs');
const path = require('path');

// ──────────────────────────────────────────────
// Project root detection
// ──────────────────────────────────────────────

/**
 * Normalize a path that may be in Git Bash format (/c/Users/...)
 * to a native Windows path (C:/Users/...) so Node.js APIs work correctly.
 */
function normalizeGitBashPath(p) {
  if (!p) return p;
  const converted = p.replace(/^\/([a-zA-Z])\//, '$1:/');
  return path.resolve(converted);
}

/**
 * Resolve project root directory.
 * Prefers $CLAUDE_PROJECT_DIR (set by Claude Code), falls back to
 * walking up from this script's location.
 */
function getProjectRoot() {
  if (process.env.CLAUDE_PROJECT_DIR) {
    return normalizeGitBashPath(process.env.CLAUDE_PROJECT_DIR);
  }
  return path.resolve(__dirname, '..', '..');
}

const PROJECT_ROOT = getProjectRoot();

// Session tracking file (gitignored)
const SESSION_FILE = path.join(__dirname, '.session-edits.json');

// ──────────────────────────────────────────────
// Module configuration — algo_beta Python modules
// ──────────────────────────────────────────────

const SERVICES = {
  fincli: {
    path: 'fincli/',
    runtime: 'python',
    testCommand: 'pytest tests/',
    lintCommand: 'ruff check fincli/',
    buildCommand: 'python -c "import fincli"',
    hasTests: true,
    testableExtensions: ['.py'],
  },
  fundainsight: {
    path: 'fundainsight/',
    runtime: 'python',
    testCommand: 'pytest tests/',
    lintCommand: 'ruff check fundainsight/',
    buildCommand: 'python -c "import fundainsight"',
    hasTests: true,
    testableExtensions: ['.py'],
  },
  core: {
    path: 'core/',
    runtime: 'python',
    testCommand: 'pytest tests/',
    lintCommand: 'ruff check core/',
    buildCommand: 'python -c "import core"',
    hasTests: true,
    testableExtensions: ['.py'],
  },
  config: {
    path: 'config/',
    runtime: 'python',
    testCommand: 'pytest tests/',
    lintCommand: 'ruff check config/',
    buildCommand: 'python -c "import config"',
    hasTests: true,
    testableExtensions: ['.py'],
  },
  logger: {
    path: 'logger/',
    runtime: 'python',
    testCommand: 'pytest tests/',
    lintCommand: 'ruff check logger/',
    buildCommand: 'python -c "import logger"',
    hasTests: true,
    testableExtensions: ['.py'],
  },
};

/**
 * Cross-module dependency map for algo_beta.
 * When a module is affected, its dependents should also be tested.
 */
const SERVICE_DEPENDENCIES = {
  core: ['fincli', 'fundainsight'],
  config: ['fincli', 'fundainsight'],
  logger: ['fincli', 'fundainsight'],
  fincli: ['fundainsight'],
};

/**
 * Expand a list of affected modules to include their dependents.
 * Prevents transitive build failures from going undetected.
 *
 * @param {string[]} services - Directly affected modules
 * @returns {string[]} Expanded list including dependent modules
 */
function expandWithDependents(services) {
  const expanded = new Set(services);
  for (const svc of services) {
    const deps = SERVICE_DEPENDENCIES[svc];
    if (deps) {
      for (const dep of deps) {
        if (SERVICES[dep]) expanded.add(dep);
      }
    }
  }
  return [...expanded];
}

// ──────────────────────────────────────────────
// Path classification
// ──────────────────────────────────────────────

const NON_TESTABLE_PATHS = [
  'workspace_output/',
  'workspace_materials/',
  'htmlcov/',
  'dist/',
  'benchmarks/',
  '__pycache__/',
  '.pytest_cache/',
  '.mypy_cache/',
  '.ruff_cache/',
  'wisdom_fruit/',
  'shared/',
  'example/',
  'src/',
  '.venv/',
  'docs/',
  '.cursor/',
  '.claude/',
  '.github/',
  '.vscode/',
  '.git/',
];

const NON_TESTABLE_EXTENSIONS = [
  '.md', '.json', '.yml', '.yaml', '.txt',
  '.env', '.gitignore', '.dockerignore',
  '.mdc', '.sql', '.sh', '.ps1', '.lock',
  '.csv', '.pstat', '.coverage',
];

// ──────────────────────────────────────────────
// Sensitive file detection
// ──────────────────────────────────────────────

const SENSITIVE_PATTERNS = [
  /\.env$/,
  /\.env\..+$/,
  /credentials\.json$/i,
  /secrets\.json$/i,
  /secrets\.ya?ml$/i,
  /\.pem$/,
  /\.key$/,
  /password\.txt$/i,
  /passwords\.txt$/i,
  /password\.json$/i,
  /service-?account.*\.json$/i,
  /\.pfx$/,
  /\.p12$/,
  /id_rsa$/,
  /id_ed25519$/,
];

// ──────────────────────────────────────────────
// Security file patterns (for OWASP checks)
// ──────────────────────────────────────────────

const SECURITY_FILE_PATTERNS = [
  /auth/i, /security/i, /jwt/i, /token/i,
  /session/i, /password/i, /crypto/i,
  /encrypt/i, /decrypt/i, /guard/i,
  /middleware/i, /interceptor/i
];

// ──────────────────────────────────────────────
// Documentation triggers — algo_beta Python patterns
// ──────────────────────────────────────────────

const DOC_TRIGGER_PATTERNS = {
  contracts: [
    /fincli\/resource\/params\/.*\.py$/,         // Finviz filter parameter definitions are query contracts
    /fundainsight\/calculators\/.*\.py$/,        // Calculator inputs/outputs are computation contracts
    /core\/configuration\/.*\.py$/,              // Configurator builds the Config contract
  ],
  architecture: [
    /fincli\/app\/main\.py$/,                    // Screening orchestration is architecture
    /fundainsight\/app\/picker\.py$/,            // Fundamental analysis pipeline is architecture
    /^[^/]+\/__main__\.py$/,                     // Module entry points define architecture
    /pyproject\.toml$/,                          // Build/dependency config is architecture
  ],
};

// ──────────────────────────────────────────────
// Detection helpers
// ──────────────────────────────────────────────

function normalizePath(filePath) {
  return filePath.replace(/\\/g, '/');
}

function detectService(filePath) {
  const normalized = normalizePath(filePath);
  for (const [name, config] of Object.entries(SERVICES)) {
    if (normalized.includes(config.path)) {
      return name;
    }
  }
  return null;
}

function isTestable(filePath) {
  const normalized = normalizePath(filePath);
  for (const p of NON_TESTABLE_PATHS) {
    if (normalized.includes(p)) return false;
  }
  const ext = path.extname(filePath).toLowerCase();
  if (NON_TESTABLE_EXTENSIONS.includes(ext)) return false;

  const service = detectService(filePath);
  if (service && SERVICES[service].hasTests) {
    return SERVICES[service].testableExtensions.includes(ext);
  }
  return false;
}

function isSensitive(filePath) {
  const normalized = normalizePath(filePath);
  const fileName = path.basename(filePath);
  return SENSITIVE_PATTERNS.some(p => p.test(fileName) || p.test(normalized));
}

function isSecurityFile(filePath) {
  const normalized = normalizePath(filePath);
  const fileName = path.basename(filePath);
  return SECURITY_FILE_PATTERNS.some(p => p.test(fileName) || p.test(normalized));
}

function getDocUpdateNeeded(filePath) {
  const normalized = normalizePath(filePath);
  const updates = [];
  if (DOC_TRIGGER_PATTERNS.contracts.some(p => p.test(normalized))) updates.push('contracts');
  if (DOC_TRIGGER_PATTERNS.architecture.some(p => p.test(normalized))) updates.push('architecture');
  return updates;
}

function getServiceConfig(serviceName) {
  return SERVICES[serviceName] || null;
}

// ──────────────────────────────────────────────
// Session tracking
// ──────────────────────────────────────────────

function loadSession() {
  try {
    if (fs.existsSync(SESSION_FILE)) {
      const raw = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8'));
      // Restore arrays that represent sets
      raw.affectedServices = raw.affectedServices || [];
      raw.docsToUpdate = raw.docsToUpdate || [];
      raw.editedFiles = raw.editedFiles || [];
      raw.securityFilesEdited = raw.securityFilesEdited || [];
      return raw;
    }
  } catch { /* return fresh session */ }

  return {
    startTime: new Date().toISOString(),
    editedFiles: [],
    affectedServices: [],
    hasTestableChanges: false,
    hasSecurityChanges: false,
    docsToUpdate: [],
    securityFilesEdited: []
  };
}

function saveSession(session) {
  // Deduplicate arrays before saving
  const toSave = {
    ...session,
    affectedServices: [...new Set(session.affectedServices)],
    docsToUpdate: [...new Set(session.docsToUpdate)]
  };
  fs.writeFileSync(SESSION_FILE, JSON.stringify(toSave, null, 2));
}

function trackEdit(filePath) {
  const session = loadSession();

  if (!session.editedFiles.includes(filePath)) {
    session.editedFiles.push(filePath);
  }

  const service = detectService(filePath);
  if (service && !session.affectedServices.includes(service)) {
    session.affectedServices.push(service);
  }

  if (isTestable(filePath)) {
    session.hasTestableChanges = true;
  }

  if (isSecurityFile(filePath)) {
    session.hasSecurityChanges = true;
    if (!session.securityFilesEdited.includes(filePath)) {
      session.securityFilesEdited.push(filePath);
    }
  }

  const docUpdates = getDocUpdateNeeded(filePath);
  for (const docType of docUpdates) {
    if (!session.docsToUpdate.includes(docType)) {
      session.docsToUpdate.push(docType);
    }
  }

  saveSession(session);
  return session;
}

function clearSession() {
  try {
    if (fs.existsSync(SESSION_FILE)) fs.unlinkSync(SESSION_FILE);
  } catch { /* ignore */ }
}

// ──────────────────────────────────────────────
// I/O helpers for Claude Code hooks
// ──────────────────────────────────────────────

/**
 * Read JSON from stdin (Claude Code sends hook context here).
 */
function readStdin() {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => {
      try { resolve(JSON.parse(data)); }
      catch { resolve({}); }
    });
    process.stdin.on('error', () => resolve({}));
  });
}

/**
 * Exit 0 with JSON on stdout — success, action proceeds.
 * Claude Code parses: continue, stopReason, suppressOutput, systemMessage,
 * and hookSpecificOutput (for PreToolUse/PermissionRequest).
 */
function respondOk(json) {
  if (json && Object.keys(json).length > 0) {
    process.stdout.write(JSON.stringify(json));
  }
  process.exit(0);
}

/**
 * Exit 2 with message on stderr — blocking error.
 * Only effective for blocking-capable events (PreToolUse, UserPromptSubmit, Stop).
 * The stderr message is fed back to Claude as context.
 */
function respondBlock(message) {
  process.stderr.write(message);
  process.exit(2);
}

module.exports = {
  PROJECT_ROOT,
  SERVICES,
  SERVICE_DEPENDENCIES,
  NON_TESTABLE_PATHS,
  NON_TESTABLE_EXTENSIONS,
  SECURITY_FILE_PATTERNS,
  DOC_TRIGGER_PATTERNS,
  normalizeGitBashPath,
  normalizePath,
  detectService,
  isTestable,
  isSensitive,
  isSecurityFile,
  getDocUpdateNeeded,
  getServiceConfig,
  expandWithDependents,
  loadSession,
  saveSession,
  trackEdit,
  clearSession,
  readStdin,
  respondOk,
  respondBlock
};
