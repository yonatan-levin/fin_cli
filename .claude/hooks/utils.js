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
const { spawnSync } = require('child_process');

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
  fincli_api: {
    path: 'fincli_api/',
    runtime: 'python',
    testCommand: 'pytest tests/',
    lintCommand: 'ruff check fincli_api/',
    buildCommand: 'python -c "import fincli_api"',
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
  singleton: {
    path: 'singleton.py',
    runtime: 'python',
    testCommand: 'pytest tests/',
    lintCommand: 'ruff check singleton.py',
    buildCommand: 'python -c "import singleton"',
    hasTests: true,
    testableExtensions: ['.py'],
  },
};

/**
 * Cross-module dependency map for algo_beta.
 * When a module is affected, its dependents should also be tested.
 */
const SERVICE_DEPENDENCIES = {
  fincli: ['fincli_api'],
  core: ['fincli', 'fincli_api'],
  config: ['fincli', 'fincli_api'],
  logger: ['fincli', 'fincli_api'],
  singleton: ['fincli', 'fincli_api'],
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
    /core\/configuration\/.*\.py$/,              // Configurator builds the Config contract
  ],
  architecture: [
    /fincli\/app\/main\.py$/,                    // Screening orchestration is architecture
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

/**
 * Walk up from a file to its git tree root (`.git` dir or worktree `.git` file).
 * Returns null when the file is not inside any git tree.
 */
function findTreeRoot(filePath) {
  let dir = path.dirname(path.resolve(filePath));
  for (;;) {
    if (fs.existsSync(path.join(dir, '.git'))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

/**
 * Main-checkout root for a worktree tree root (its `.git` FILE points at
 * `<main>/.git/worktrees/<name>`). Returns null for a normal checkout.
 */
function mainRepoRootOf(treeRoot) {
  try {
    const gitPath = path.join(treeRoot, '.git');
    if (!fs.statSync(gitPath).isFile()) return null;
    const m = fs.readFileSync(gitPath, 'utf8').match(/^gitdir:\s*(.+)$/m);
    if (!m) return null;
    // <main>/.git/worktrees/<name> → <main>
    return path.resolve(m[1].trim(), '..', '..', '..');
  } catch { return null; }
}

/**
 * Gate tools that check or execute project code. These must come from a
 * project venv — NEVER from PATH: a PATH-resolved interpreter belongs to some
 * other environment and gates that environment, not this tree (2026-08-12: a
 * machine-global pytest with an incompatible pytest-asyncio masqueraded as a
 * red repo gate). `pytest` is stricter still: it IMPORTS the code under test,
 * and any out-of-tree venv resolves `fincli` through its own editable install
 * — i.e. it would silently test a DIFFERENT tree — so it may only come from
 * the gated tree's own venv.
 */
const VENV_ONLY_TOOLS = new Set(['ruff', 'mypy', 'pytest']);

/**
 * Resolve a gate tool to the project venv when available (hooks inherit a PATH
 * that usually lacks ruff/mypy/pytest — they live in .venv/Scripts).
 *
 * ruff/mypy try the gated tree's venv, then this checkout's, then the main
 * checkout's (binary-only tools: any pinned copy judges the tree honestly).
 * pytest tries the gated tree's venv ONLY (see VENV_ONLY_TOOLS). Venv-only
 * tools return null when no venv executable exists — callers must surface a
 * blocking "create the venv" failure instead of falling back to PATH. Other
 * commands (git, pip-audit) still fall back to the bare name (PATH lookup).
 */
function resolveTool(file, gateCwd) {
  if (file.includes('/') || file.includes('\\')) return file; // already a path
  const roots = file === 'pytest'
    ? [gateCwd].filter(Boolean)
    : [gateCwd, PROJECT_ROOT, gateCwd && mainRepoRootOf(gateCwd)].filter(Boolean);
  const suffixes = process.platform === 'win32'
    ? [`Scripts/${file}.exe`, `Scripts/${file}.cmd`, `Scripts/${file}`]
    : [`bin/${file}`];
  for (const root of roots) {
    for (const suffix of suffixes) {
      const candidate = path.join(root, '.venv', suffix);
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return VENV_ONLY_TOOLS.has(file) ? null : file; // PATH fallback: non-gate tools only
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
  // Exclusions match against the path RELATIVE to the file's own git tree, so
  // files inside a worktree under `.claude/worktrees/<name>/` are judged by
  // their in-repo path, not by the worktree's location.
  const treeRoot = findTreeRoot(filePath);
  const normalized = normalizePath(
    treeRoot ? path.relative(treeRoot, path.resolve(filePath)) : filePath
  );
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
// Process execution
// ──────────────────────────────────────────────

/**
 * Run a command with an argument array and return a bounded, structured result.
 *
 * Windows uses its command shell only to resolve Python's generated `.cmd`
 * launchers; callers still pass arguments separately rather than interpolating
 * edited paths into a command string.
 */
function runCommand(name, command, args, options = {}) {
  const cwd = options.cwd || PROJECT_ROOT;
  const timeout = options.timeout || 300000;
  const commandText = [command, ...args].join(' ');

  if (!fs.existsSync(cwd)) {
    return {
      success: false,
      name,
      command: commandText,
      kind: 'infrastructure',
      output: `Working directory does not exist: ${cwd}`,
    };
  }

  // Resolve the tool from the gated tree's venv first (hooks inherit a PATH
  // that usually lacks ruff/mypy/pytest — they live in .venv/Scripts).
  let executable = resolveTool(command, cwd);

  // Venv-only gate tool with no venv executable: block honestly instead of
  // running whatever interpreter PATH happens to expose (see VENV_ONLY_TOOLS).
  if (executable === null) {
    const searched = command === 'pytest'
      ? `${cwd}${path.sep}.venv (pytest must run from the gated tree's own venv — an ` +
        'out-of-tree venv would import a different tree via its editable install)'
      : 'the gated tree, hook checkout, and main checkout .venv dirs';
    return {
      success: false,
      name,
      command: commandText,
      kind: 'unavailable',
      status: null,
      executable: null,
      output:
        `gate tool '${command}' has no project-venv executable; searched ${searched}. ` +
        'PATH fallback is refused for venv-only gate tools. Fix (run inside the gated ' +
        'tree): python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]" ' +
        '(.venv/bin/python on POSIX)',
    };
  }

  let executableArgs = args;
  let windowsVerbatimArguments = false;

  if (executable === command && process.platform === 'win32') {
    // No venv hit (non-gate tool) — fall back to a PATH lookup so .cmd/.bat
    // launchers can be identified and wrapped below.
    const lookup = spawnSync('where.exe', [command], {
      encoding: 'utf8',
      windowsHide: true,
      shell: false,
    });
    const resolved = (lookup.stdout || '').split(/\r?\n/).find(Boolean);
    if (resolved) executable = resolved;
  }

  // The executable actually judging this gate — recorded on every result so a
  // failure names the interpreter it came from (a PATH/global tool once
  // masqueraded as a red repo gate; see VENV_ONLY_TOOLS).
  const resolvedExecutable = executable;

  if (process.platform === 'win32' && /\.(cmd|bat)$/i.test(executable)) {
    // .cmd/.bat launchers (venv- or PATH-resolved) need an explicit cmd.exe
    // wrapper — Node refuses to spawn them with shell:false.
    const quote = value => `"${String(value).replace(/%/g, '%%').replace(/"/g, '""')}"`;
    const commandLine = `${quote(executable)} ${args.map(quote).join(' ')}`;
    executable = process.env.COMSPEC || 'cmd.exe';
    executableArgs = ['/d', '/s', '/c', `"${commandLine}"`];
    windowsVerbatimArguments = true;
  }

  const result = spawnSync(executable, executableArgs, {
    cwd,
    encoding: 'utf8',
    timeout,
    windowsHide: true,
    shell: false,
    windowsVerbatimArguments,
  });
  const output = `${result.stdout || ''}${result.stderr || ''}`.trim().substring(0, 1200);

  if (result.error) {
    const timedOut = result.error.code === 'ETIMEDOUT';
    return {
      success: false,
      name,
      command: commandText,
      kind: timedOut ? 'timeout' : 'unavailable',
      status: null,
      executable: resolvedExecutable,
      output: (output || result.error.message).substring(0, 1200),
    };
  }

  return {
    success: result.status === 0,
    name,
    command: commandText,
    kind: result.status === 0 ? 'success' : 'non-zero',
    status: result.status,
    executable: resolvedExecutable,
    output,
  };
}

function formatCommandFailure(result) {
  // Name the interpreter/binary that produced the verdict — a red gate from
  // the wrong environment must be diagnosable from the failure text alone.
  const via = result.executable && result.executable !== result.command.split(' ')[0]
    ? `\nvia: ${result.executable}`
    : '';
  const detail = result.output ? `\n${result.output}` : '';
  return `${result.name} failed (${result.command}; ${result.kind})${via}${detail}`;
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
  findTreeRoot,
  mainRepoRootOf,
  resolveTool,
  detectService,
  isTestable,
  isSensitive,
  isSecurityFile,
  getDocUpdateNeeded,
  getServiceConfig,
  runCommand,
  formatCommandFailure,
  expandWithDependents,
  loadSession,
  saveSession,
  trackEdit,
  clearSession,
  readStdin,
  respondOk,
  respondBlock
};
