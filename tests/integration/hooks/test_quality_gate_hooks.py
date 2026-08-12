from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING

import pytest
from conftest import write_tool_wrapper

if TYPE_CHECKING:
    from .conftest import HookSandbox


def _testable_session(sandbox: HookSandbox) -> None:
    edited_file = sandbox.write_file("fincli/example.py", "value: int = 1\n")
    sandbox.seed_session(edited_file)


def test_on_stop_blocks_when_aggregate_coverage_is_below_90(
    hook_sandbox: HookSandbox,
) -> None:
    _testable_session(hook_sandbox)

    result = hook_sandbox.run("on-stop.js", {}, HOOK_FAIL_COVERAGE="1")

    assert result.returncode == 2
    assert "Tests and aggregate coverage failed" in result.stderr
    assert "TOTAL 100 11 89%" in result.stderr
    pytest_calls = [call for call in hook_sandbox.command_calls() if call["tool"] == "pytest"]
    assert pytest_calls == [
        {
            "tool": "pytest",
            "args": ["tests/", "--cov", "--cov-report=term-missing"],
        }
    ]


def test_on_stop_blocks_when_strict_mypy_fails(hook_sandbox: HookSandbox) -> None:
    _testable_session(hook_sandbox)

    result = hook_sandbox.run("on-stop.js", {}, HOOK_FAIL_MYPY="1")

    assert result.returncode == 2
    assert "Strict mypy failed" in result.stderr
    assert "incompatible types" in result.stderr
    mypy_calls = [call for call in hook_sandbox.command_calls() if call["tool"] == "mypy"]
    assert mypy_calls == [{"tool": "mypy", "args": []}]


@pytest.mark.parametrize(
    ("environment_name", "diagnostic"),
    [
        ("HOOK_FAIL_RUFF_LINT", "Lint (ruff) failed"),
        ("HOOK_FAIL_RUFF_FORMAT", "Format (ruff format --check) failed"),
    ],
)
def test_on_stop_blocks_when_ruff_gate_fails(
    hook_sandbox: HookSandbox,
    environment_name: str,
    diagnostic: str,
) -> None:
    _testable_session(hook_sandbox)

    result = hook_sandbox.run("on-stop.js", {}, **{environment_name: "1"})

    assert result.returncode == 2
    assert diagnostic in result.stderr


def test_on_stop_all_required_gates_green_exits_zero(
    hook_sandbox: HookSandbox,
) -> None:
    _testable_session(hook_sandbox)

    result = hook_sandbox.run("on-stop.js", {})

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["systemMessage"].startswith("All required quality gates passed")


def test_on_stop_loop_guard_exits_zero_without_running_commands(
    hook_sandbox: HookSandbox,
) -> None:
    result = hook_sandbox.run(
        "on-stop.js",
        {"stop_hook_active": True},
        HOOK_FAIL_COMMANDS="1",
    )

    assert result.returncode == 0
    assert hook_sandbox.command_calls() == []


def test_post_edit_blocks_on_deliberate_type_error(
    hook_sandbox: HookSandbox,
) -> None:
    edited_file = hook_sandbox.write_file(
        "fincli/deliberate_type_error.py",
        'value: int = "wrong"\n',
    )
    original = edited_file.read_text(encoding="utf-8")

    result = hook_sandbox.run(
        "post-edit.js",
        {"tool_input": {"file_path": str(edited_file)}},
        HOOK_FAIL_MYPY="1",
    )

    assert result.returncode == 2
    assert "REQUIRED ACTION" in result.stderr
    assert "Strict mypy failed" in result.stderr
    assert "saved edit remains" in result.stderr
    assert edited_file.read_text(encoding="utf-8") == original


def test_post_edit_blocks_when_final_ruff_check_fails(
    hook_sandbox: HookSandbox,
) -> None:
    edited_file = hook_sandbox.write_file("fincli/deliberate.py", "value = 1\n")

    result = hook_sandbox.run(
        "post-edit.js",
        {"tool_input": {"file_path": str(edited_file)}},
        HOOK_FAIL_RUFF_FINAL="1",
    )

    assert result.returncode == 2
    assert "Ruff final check failed" in result.stderr


def test_post_edit_clean_python_file_exits_zero(hook_sandbox: HookSandbox) -> None:
    edited_file = hook_sandbox.write_file("fincli/clean.py", "value: int = 1\n")

    result = hook_sandbox.run(
        "post-edit.js",
        {"tool_input": {"file_path": str(edited_file)}},
    )

    assert result.returncode == 0
    calls = hook_sandbox.command_calls()
    assert [call["args"][:2] for call in calls if call["tool"] == "ruff"] == [
        ["check", "--fix"],
        ["format", str(edited_file)],
        ["check", str(edited_file)],
        ["format", "--check"],
    ]
    assert [call["args"] for call in calls if call["tool"] == "mypy"] == [[str(edited_file)]]


def test_on_stop_refuses_path_gate_tools_when_venv_is_missing(
    hook_sandbox: HookSandbox,
) -> None:
    """Venv-only gate tools must never run from PATH.

    Regression pin for the 2026-08-12 incident where a machine-global pytest
    (with an incompatible plugin) masqueraded as a red repo gate. PATH shims
    for ruff/mypy/pytest ARE present here; the project venv is deleted. The
    hook must block with the create-the-venv diagnostic WITHOUT invoking any
    of the three — proving the PATH fallback is gone, not merely deprioritized.
    """
    _testable_session(hook_sandbox)
    path_bin = hook_sandbox.tool_runner.parent
    for tool in ("ruff", "mypy", "pytest"):
        write_tool_wrapper(path_bin, tool, hook_sandbox.tool_runner)
    shutil.rmtree(hook_sandbox.project_root / ".venv")

    result = hook_sandbox.run("on-stop.js", {})

    assert result.returncode == 2
    assert "no project-venv executable" in result.stderr
    assert "PATH fallback is refused" in result.stderr
    gate_calls = [
        call for call in hook_sandbox.command_calls() if call["tool"] in {"ruff", "mypy", "pytest"}
    ]
    assert gate_calls == []


def test_on_stop_pytest_requires_the_gated_trees_own_venv(
    hook_sandbox: HookSandbox,
) -> None:
    """pytest may not fall back to another venv; ruff/mypy may.

    Pins the differential policy: a gated tree (own ``.git/``, no ``.venv``)
    is seeded while the hook checkout's venv shims exist. ruff/mypy resolve
    through the fallback chain and run; pytest — which would import a
    DIFFERENT tree via that venv's editable install — must be refused with
    the gated-tree-only diagnostic instead.
    """
    tree = hook_sandbox.project_root.parent / "gated_tree"
    (tree / ".git").mkdir(parents=True)
    edited_file = tree / "fincli" / "example.py"
    edited_file.parent.mkdir(parents=True)
    edited_file.write_text("value: int = 1\n", encoding="utf-8")
    hook_sandbox.seed_session(edited_file)

    result = hook_sandbox.run("on-stop.js", {})

    assert result.returncode == 2
    assert "no project-venv executable" in result.stderr
    assert "gated tree's own venv" in result.stderr
    tools = {call["tool"] for call in hook_sandbox.command_calls()}
    assert {"ruff", "mypy"} <= tools
    assert "pytest" not in tools


def test_post_edit_markdown_skips_code_gates(hook_sandbox: HookSandbox) -> None:
    edited_file = hook_sandbox.write_file("docs/note.md", "# Note\n")

    result = hook_sandbox.run(
        "post-edit.js",
        {"tool_input": {"file_path": str(edited_file)}},
        HOOK_FAIL_COMMANDS="1",
    )

    assert result.returncode == 0
    assert hook_sandbox.command_calls() == []
