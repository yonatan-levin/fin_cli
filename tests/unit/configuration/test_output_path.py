"""Regression tests pinning today's `Config.file_path()` semantics.

The pipeline-mode refactor (docs/features/pipeline-mode-spec.md, Pillar 2 in
Task 4) introduces `--output PATH` and `FINCLI_OUTPUT_DIR` env-var support and
will rework this method's contract. Before that lands, these tests pin the
currently-shipped behavior so the refactor cannot silently regress the default
CWD-relative output path.

Pinned facts (from `config/config.py:Config.file_path` as of this commit):
  - returns `os.path.join(os.getcwd(), "workspace_output/{name}_{YYYY-MM-DD_HH-MM}.csv")`
  - the path is **CWD-relative**, not anchored to the repo root or user-data dir
  - the timestamp resolves at call time
  - any leading directory component supplied by `name` is preserved verbatim
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from config.config import Config

# Matches the project-standard timestamp format `YYYY-MM-DD_HH-MM`.
_TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}")


def test_file_path_returns_cwd_relative_workspace_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`Config.file_path("stock_screener")` must resolve under CWD/workspace_output/."""
    monkeypatch.chdir(tmp_path)

    result = Config.file_path("stock_screener")

    expected_dir = os.path.join(str(tmp_path), "workspace_output")
    assert result.startswith(expected_dir), f"Expected path under {expected_dir}, got: {result}"


def test_file_path_includes_timestamp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The generated filename must embed a `YYYY-MM-DD_HH-MM` timestamp.

    Pinning the format lets multiple runs in a single hour coexist without
    collision (per CONTRACTS §3 file naming rule).
    """
    monkeypatch.chdir(tmp_path)

    result = Config.file_path("stock_screener")
    filename = os.path.basename(result)

    assert filename.startswith("stock_screener_"), filename
    assert filename.endswith(".csv"), filename
    assert _TIMESTAMP_PATTERN.search(filename) is not None, (
        f"No YYYY-MM-DD_HH-MM timestamp in filename: {filename}"
    )


def test_file_path_changes_with_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Switching CWD must change the returned path — the method is not anchored.

    This is the key regression to pin: the upcoming refactor will let
    `FINCLI_OUTPUT_DIR` and `--output` override the default. The default itself
    must remain CWD-relative so today's `./workspace_output/...` UX survives.
    """
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    monkeypatch.chdir(first)
    path_first = Config.file_path("stock_screener")
    assert os.path.dirname(path_first).startswith(str(first))

    monkeypatch.chdir(second)
    path_second = Config.file_path("stock_screener")
    assert os.path.dirname(path_second).startswith(str(second))

    assert path_first != path_second
