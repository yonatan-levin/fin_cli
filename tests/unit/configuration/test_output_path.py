"""Tests pinning `Config.file_path()` semantics across all four precedence tiers.

The pipeline-mode refactor (docs/features/pipeline-mode-spec.md, Pillar 2 in
Task 4) introduces `--output PATH` and `FINCLI_OUTPUT_DIR` env-var support.
This file covers:

  - Back-compat: with no `output_path` and no `output_dir` set, the default
    resolves to `<CWD>/workspace_output/{name}_{date}.csv` exactly as today.
  - New: `output_dir` (populated from `FINCLI_OUTPUT_DIR`) overrides the
    parent directory while preserving the timestamped basename.
  - New: `output_path` (populated from `--output PATH`) overrides everything
    and is returned verbatim — no timestamp added.
  - New: the `-` sentinel (stdout-streaming marker) is **not** treated as a
    file path; `file_path()` falls back to the timestamped default so the
    stdout dispatch in `run_stock_screener` happens at the call site, not
    inside the path resolver.
  - New: precedence is `output_path` > `output_dir` > default.
  - Builder integration: `build_config(output_path=...)` populates
    `Config.output_path`; the `FINCLI_OUTPUT_DIR` env var populates
    `Config.output_dir`.

Pinned facts (from `config/config.py:Config.file_path` post-refactor):
  - returns `os.path.join(os.getcwd(), "workspace_output/{name}_{YYYY-MM-DD_HH-MM}.csv")`
    when neither override is set
  - the path is **CWD-relative**, not anchored to the repo root or user-data dir
  - the timestamp resolves at call time
  - `output_path` (when set and not `-`) is returned verbatim
  - `output_dir` (when set) replaces only the parent directory
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from config.config import Config
from core.configuration.configurator import build_config

# Matches the project-standard timestamp format `YYYY-MM-DD_HH-MM`.
_TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}")


# ---------------------------------------------------------------------------
# Default tier — no output_path, no output_dir → CWD-relative workspace_output/.
# ---------------------------------------------------------------------------


def test_file_path_returns_cwd_relative_workspace_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`Config().file_path("stock_screener")` must resolve under CWD/workspace_output/."""
    monkeypatch.chdir(tmp_path)

    result = Config().file_path("stock_screener")

    expected_dir = os.path.join(str(tmp_path), "workspace_output")
    assert result.startswith(expected_dir), f"Expected path under {expected_dir}, got: {result}"


def test_file_path_includes_timestamp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The generated filename must embed a `YYYY-MM-DD_HH-MM` timestamp.

    Pinning the format lets multiple runs in a single hour coexist without
    collision (per CONTRACTS §3 file naming rule).
    """
    monkeypatch.chdir(tmp_path)

    result = Config().file_path("stock_screener")
    filename = os.path.basename(result)

    assert filename.startswith("stock_screener_"), filename
    assert filename.endswith(".csv"), filename
    assert _TIMESTAMP_PATTERN.search(filename) is not None, (
        f"No YYYY-MM-DD_HH-MM timestamp in filename: {filename}"
    )


def test_file_path_changes_with_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Switching CWD must change the returned path — the default is not anchored.

    The upcoming refactor lets `FINCLI_OUTPUT_DIR` and `--output` override the
    default, but the default itself must remain CWD-relative so today's
    `./workspace_output/...` UX survives.
    """
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    monkeypatch.chdir(first)
    path_first = Config().file_path("stock_screener")
    assert os.path.dirname(path_first).startswith(str(first))

    monkeypatch.chdir(second)
    path_second = Config().file_path("stock_screener")
    assert os.path.dirname(path_second).startswith(str(second))

    assert path_first != path_second


# ---------------------------------------------------------------------------
# `output_dir` tier — env-var override of parent directory only.
# ---------------------------------------------------------------------------


def test_output_dir_overrides_parent_directory(tmp_path: Path) -> None:
    """`Config(output_dir=<dir>).file_path("x")` writes basename under `<dir>`.

    The basename keeps its `{name}_{timestamp}.csv` shape — only the parent
    directory is replaced. Pins precedence tier 3 from spec §5.2.
    """
    config = Config(output_dir=tmp_path)

    result = config.file_path("stock_screener")

    assert os.path.dirname(result) == str(tmp_path)
    filename = os.path.basename(result)
    assert filename.startswith("stock_screener_"), filename
    assert filename.endswith(".csv"), filename
    assert _TIMESTAMP_PATTERN.search(filename) is not None, filename


# ---------------------------------------------------------------------------
# `output_path` tier — exact destination, no timestamp, wins over output_dir.
# ---------------------------------------------------------------------------


def test_output_path_returned_verbatim(tmp_path: Path) -> None:
    """`Config(output_path=<path>).file_path("x")` returns `<path>` unmodified.

    No timestamp is injected; the caller pinned the exact destination.
    """
    target = tmp_path / "custom" / "out.csv"
    config = Config(output_path=str(target))

    result = config.file_path("stock_screener")

    assert result == str(target)


def test_output_path_overrides_output_dir(tmp_path: Path) -> None:
    """`output_path` set → `output_dir` is ignored (most-explicit wins).

    Pins precedence tier 1 > tier 3 from spec §5.2.
    """
    explicit = tmp_path / "explicit.csv"
    env_dir = tmp_path / "env_dir"
    config = Config(output_path=str(explicit), output_dir=env_dir)

    result = config.file_path("stock_screener")

    assert result == str(explicit)
    # Sanity: the env_dir override must not have leaked into the result.
    assert str(env_dir) not in result


def test_dash_sentinel_not_treated_as_file_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`Config(output_path="-").file_path("x")` falls through to the default.

    The `-` sentinel is a stdout-streaming marker, not a literal path. The
    file-path resolver intentionally ignores it so the stdout dispatch is
    handled at the orchestrator boundary (`run_stock_screener` checks
    `config.output_path == "-"` before calling `file_path`). Without this
    carve-out a downstream caller that did call `file_path` would attempt
    to write to a file literally named `-`.
    """
    monkeypatch.chdir(tmp_path)
    config = Config(output_path="-")

    result = config.file_path("stock_screener")

    # Falls through to the default — same shape as the no-overrides case.
    expected_dir = os.path.join(str(tmp_path), "workspace_output")
    assert result.startswith(expected_dir), result


# ---------------------------------------------------------------------------
# Builder integration — `build_config` reads FINCLI_OUTPUT_DIR + output_path.
# ---------------------------------------------------------------------------


def test_build_config_threads_output_path(tmp_path: Path) -> None:
    """`build_config(output_path=<path>)` populates `Config.output_path`."""
    target = tmp_path / "out.csv"

    config = build_config(output_path=str(target))

    assert config.output_path == str(target)


def test_build_config_reads_fincli_output_dir_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`FINCLI_OUTPUT_DIR=<dir>` is read by `build_config` into `Config.output_dir`.

    Mirrors the `HISTORY_DIR` env-var precedent in `configurator.py`.
    """
    monkeypatch.setenv("FINCLI_OUTPUT_DIR", str(tmp_path))

    config = build_config()

    assert config.output_dir == tmp_path


def test_build_config_no_env_no_arg_leaves_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No `output_path` arg and no `FINCLI_OUTPUT_DIR` env → defaults intact."""
    monkeypatch.delenv("FINCLI_OUTPUT_DIR", raising=False)

    config = build_config()

    assert config.output_path == ""
    assert config.output_dir is None


def test_output_path_arg_wins_over_fincli_output_dir_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`build_config(output_path=PATH)` + `FINCLI_OUTPUT_DIR=DIR` → PATH wins.

    End-to-end precedence test: both sources are populated in `Config`, but
    `file_path()` returns the explicit path unchanged.
    """
    explicit = tmp_path / "explicit.csv"
    env_dir = tmp_path / "env_dir"
    monkeypatch.setenv("FINCLI_OUTPUT_DIR", str(env_dir))

    config = build_config(output_path=str(explicit))

    # Both fields are populated on Config…
    assert config.output_path == str(explicit)
    assert config.output_dir == env_dir
    # …but `file_path` returns the explicit path verbatim (precedence holds).
    assert config.file_path("stock_screener") == str(explicit)
