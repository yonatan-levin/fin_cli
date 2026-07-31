from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_NAMES = ("on-stop.js", "post-edit.js", "utils.js")


@dataclass
class HookSandbox:
    project_root: Path
    hook_dir: Path
    command_log: Path
    environment: dict[str, str]

    def write_file(self, relative_path: str, content: str) -> Path:
        file_path = self.project_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def seed_session(self, edited_file: Path) -> None:
        session = {
            "editedFiles": [str(edited_file)],
            "affectedServices": ["fincli"],
            "hasTestableChanges": True,
            "hasSecurityChanges": False,
            "docsToUpdate": [],
            "securityFilesEdited": [],
            "skillsReminded": True,
        }
        (self.hook_dir / ".session-edits.json").write_text(
            json.dumps(session),
            encoding="utf-8",
        )

    def run(
        self,
        hook_name: str,
        hook_input: dict[str, Any],
        **environment_overrides: str,
    ) -> subprocess.CompletedProcess[str]:
        environment = self.environment | environment_overrides
        return subprocess.run(
            ["node", str(self.hook_dir / hook_name)],
            input=json.dumps(hook_input),
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )

    def command_calls(self) -> list[dict[str, Any]]:
        if not self.command_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.command_log.read_text(encoding="utf-8").splitlines()
            if line
        ]


def _write_fake_toolchain(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    command_log = tmp_path / "commands.jsonl"
    runner = bin_dir / "tool_runner.py"
    runner.write_text(
        """
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


tool = sys.argv[1]
arguments = sys.argv[2:]
with Path(os.environ["HOOK_COMMAND_LOG"]).open("a", encoding="utf-8") as log:
    log.write(json.dumps({"tool": tool, "args": arguments}) + "\\n")

if os.environ.get("HOOK_FAIL_COMMANDS") == "1":
    print(f"unexpected command: {tool}", file=sys.stderr)
    raise SystemExit(1)

if tool == "mypy" and os.environ.get("HOOK_FAIL_MYPY") == "1":
    print("deliberate_type_error.py:1: error: incompatible types", file=sys.stderr)
    raise SystemExit(1)

if tool == "pytest" and os.environ.get("HOOK_FAIL_COVERAGE") == "1":
    print("TOTAL 100 11 89%", file=sys.stderr)
    print("Coverage failure: total of 89 is below fail-under=90", file=sys.stderr)
    raise SystemExit(1)

if (
    tool == "ruff"
    and arguments[:2] == ["check", "."]
    and os.environ.get("HOOK_FAIL_RUFF_LINT") == "1"
):
    print("repo.py:1:1: F401 unused import", file=sys.stderr)
    raise SystemExit(1)

if (
    tool == "ruff"
    and arguments[:3] == ["format", "--check", "."]
    and os.environ.get("HOOK_FAIL_RUFF_FORMAT") == "1"
):
    print("Would reformat: repo.py", file=sys.stderr)
    raise SystemExit(1)

if (
    tool == "ruff"
    and arguments[:1] == ["check"]
    and "--fix" not in arguments
    and arguments[-1:] != ["."]
    and os.environ.get("HOOK_FAIL_RUFF_FINAL") == "1"
):
    print("deliberate.py:1:1: F401 unused import", file=sys.stderr)
    raise SystemExit(1)
""".lstrip(),
        encoding="utf-8",
    )

    for tool in ("git", "mypy", "pip-audit", "pytest", "ruff"):
        if os.name == "nt":
            wrapper = bin_dir / f"{tool}.cmd"
            wrapper.write_text(
                '@set "COV_CORE_SOURCE="\n'
                '@set "COV_CORE_CONFIG="\n'
                '@set "COV_CORE_DATAFILE="\n'
                f'@"{sys.executable}" "{runner}" "{tool}" %*\n',
                encoding="utf-8",
            )
        else:
            wrapper = bin_dir / tool
            wrapper.write_text(
                "#!/bin/sh\n"
                "unset COV_CORE_SOURCE COV_CORE_CONFIG COV_CORE_DATAFILE\n"
                f'exec "{sys.executable}" "{runner}" "{tool}" "$@"\n',
                encoding="utf-8",
            )
            wrapper.chmod(0o755)

    return bin_dir, command_log


@pytest.fixture
def hook_sandbox(tmp_path: Path) -> HookSandbox:
    project_root = tmp_path / "project"
    hook_dir = project_root / ".claude" / "hooks"
    hook_dir.mkdir(parents=True)
    for hook_name in HOOK_NAMES:
        shutil.copy2(REPO_ROOT / ".claude" / "hooks" / hook_name, hook_dir / hook_name)

    for directory in ("fincli", "fincli_api", "core", "config", "logger", "tests"):
        (project_root / directory).mkdir()
    (project_root / "singleton.py").write_text("", encoding="utf-8")

    bin_dir, command_log = _write_fake_toolchain(tmp_path)
    environment = os.environ.copy()
    environment.update(
        {
            "CLAUDE_HOOK_DEPENDENCY_AUDIT": "false",
            "CLAUDE_PROJECT_DIR": str(project_root),
            "HOOK_COMMAND_LOG": str(command_log),
            "PATH": os.pathsep.join((str(bin_dir), environment["PATH"])),
        }
    )
    return HookSandbox(project_root, hook_dir, command_log, environment)
