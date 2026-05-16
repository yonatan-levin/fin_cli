"""Screener pipeline orchestrator.

Wires the CLI options to the screener pipeline: build query -> fetch ->
parse -> DataFrame -> write CSV. Owns the four pillars of pipeline mode
(`docs/features/archive/pipeline-mode-spec.md`):

  * Pillar 1 — structured filter input flows in through ``filters`` (the
    CLI normalizes ``--filter`` / ``--filters-json`` / ``--filters-file``
    into a JSON string).
  * Pillar 2 — output destination dispatch keyed on ``config.output_path``
    (``-`` sentinel = stream to stdout, anything else = file path).
  * Pillar 3 — stream discipline plus the ``--quiet`` / ``--json-summary``
    knobs; ``_emit_run_tail`` is the single chokepoint that writes the
    ``OUTPUT_PATH=`` discovery line (always) and the JSON summary (when
    ``--json-summary`` is set).
  * Pillar 4 — differentiated exit codes via ``exit_codes.classify``; a
    try/except wrapper around the pipeline maps unhandled exceptions to
    SUCCESS / UPSTREAM / DATA / INTERNAL before threading the code into
    both the summary and ``sys.exit``.

The ``--output -`` carve-out for the ``Ticker`` column (spec §5.6) lives
in ``build_data_frame``: file destinations keep the Excel
``=HYPERLINK(...)`` wrap; stdout streaming writes the raw symbol so
``pandas.read_csv`` consumers downstream are not poisoned by formulas.
"""

from __future__ import annotations

import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from config.config import STDOUT_SENTINEL
from core.configuration import configurator
from fincli.app import exit_codes
from fincli.cli.cli_stock_screener import select_filters_and_values
from fincli.stock_screening.content.stock_table import StockTableScreeningContent
from fincli.stock_screening.locators.stock_table_locators import StockTableLocators
from fincli.utils.market_cap import convert_market_cap_to_numeric
from fincli.utils.web_scraper import fetch_page_sync
from logger.logger import logger

# Pillar 3 JSON summary contract (`docs/features/archive/pipeline-mode-spec.md` §5.3.4).
# Pinned to 1 from day one so downstream parsers can branch on the field from
# the very first emission. Bump on any breaking change to the field set.
JSON_SUMMARY_SCHEMA_VERSION = 1

# Pipeline-discovery line written to stderr immediately before exit
# (regardless of --output value) so a pipeline integrator that does not want
# the JSON summary can recover the destination via
# ``tail -n1 stderr | cut -d= -f2-``. Format pinned to make the suffix the
# absolute path (or the literal ``-`` for stdout streaming). Spec §5.3.3.
OUTPUT_PATH_LINE_PREFIX = "OUTPUT_PATH="


def fetch_urls(quarry, page_count):
    urls = [f"{quarry}&r={abs(20 * (i) + 1)}" for i in range(page_count + 1)]
    return [fetch_page_sync(url) for url in urls]


def aggregate_rows(pages):
    rows = []
    for page_content in pages:
        tab = StockTableScreeningContent(page_content)
        rows.extend(tab.all_table_content)
    return [row.table_data for row in rows]


# Column order produced by `build_data_frame`: the Finviz locator order with
# `Link` dropped (it's collapsed into the Ticker `=HYPERLINK` formula for
# file output, or stripped entirely for stdout streaming) and `Symbol`
# appended as the canonical machine-readable ticker column. Pinned as a
# module-level constant so the zero-row header-only DataFrame and the
# happy-path frame share one source of truth. CONTRACTS §3.1.
_FINAL_COLUMNS: tuple[str, ...] = tuple(
    col for col in StockTableLocators.PD_TABLE_COLUMNS if col != "Link"
) + ("Symbol",)


def build_data_frame(data_rows, stream_to_stdout: bool = False):
    """Build the screener DataFrame from raw parsed rows.

    Args:
        data_rows: List of per-page row lists from ``aggregate_rows``.
        stream_to_stdout: When ``True``, skip the Excel ``=HYPERLINK(...)``
            wrap on the ``Ticker`` column and leave the raw symbol in
            place. Spec §5.6 — the formula is hostile to ``pandas.read_csv``
            consumers downstream, and stdout streaming is unambiguously a
            non-Excel context. The ``Symbol`` column stays raw in all
            modes. Default ``False`` preserves today's Excel UX for the
            file-destination paths.

    Returns:
        A pandas DataFrame with the columns declared in ``_FINAL_COLUMNS``.
        Row count matches the upstream Finviz table; column order is
        stable across modes (regression-guarded — spec §5.6 refinement E3).
    """
    df = pd.concat([pd.DataFrame(row) for row in data_rows])
    df.columns = StockTableLocators.PD_TABLE_COLUMNS
    # Coerce the Market Cap column into a nullable Float64 array so unparseable
    # cells render as empty CSV cells rather than the literal strings "nan",
    # "<NA>", or 0.0. Contract: docs/features/archive/pipeline-mode-spec.md §5.5 +
    # CONTRACTS.md §3.1.
    df["Market Cap"] = pd.array(
        [convert_market_cap_to_numeric(v) for v in df["Market Cap"]],
        dtype="Float64",
    )
    # `Symbol` is the canonical machine-readable ticker column for pipeline
    # consumers (CONTRACTS §3.1). Captured before any `Ticker` rewrite so
    # the raw symbol survives in both modes.
    df["Symbol"] = df["Ticker"]
    if not stream_to_stdout:
        # File destinations keep the Excel `=HYPERLINK(...)` wrap so opening
        # the CSV in Excel / Google Sheets gives clickable tickers. Spec
        # §5.6 — preserved exception for `--output -` only.
        df["Ticker"] = '=HYPERLINK("' + df["Link"] + '", "' + df["Ticker"] + '")'
    df.drop(columns=["Link"], axis=1, inplace=True)
    return df


def _build_empty_data_frame(stream_to_stdout: bool = False):
    """Construct a header-only DataFrame for the zero-row success path.

    Spec §5.4 — every successful run produces a discoverable output, including
    when Finviz returned zero matching tickers. Writing a header-only CSV
    (the column names + a single newline + no data rows) keeps the
    "successful run = readable CSV at OUTPUT_PATH" contract honest.

    Args:
        stream_to_stdout: Threaded through for column-set symmetry with
            ``build_data_frame``; the column order is identical between
            the two modes (``Symbol`` last regardless) so the
            ``stream_to_stdout`` parameter is unused today but kept for API
            symmetry with the happy-path builder.

    Returns:
        An empty DataFrame whose columns match ``_FINAL_COLUMNS``. Writing
        it with ``to_csv(index=False)`` produces exactly the header row.
    """
    # Suppress the unused-arg warning while keeping the symmetric signature.
    del stream_to_stdout
    return pd.DataFrame({col: [] for col in _FINAL_COLUMNS})


def _resolve_output_path_label(output_path: str, resolved_file_path: str | None) -> str:
    """Pick the value to surface as `OUTPUT_PATH=...` and `summary.output_path`.

    The literal ``-`` sentinel travels through unchanged (it is its own label
    for stdout streaming); a file destination is normalized to an absolute
    path so a pipeline consumer never has to second-guess the CWD. Spec §5.3.3
    + §5.3.4 (output_path field).

    Args:
        output_path: The original ``--output`` value (``""`` / ``"-"`` /
            an explicit path).
        resolved_file_path: The path the CSV was actually written to (the
            ``Config.file_path`` result), or ``None`` when streaming or when
            an exception fired before the path was resolved.

    Returns:
        The string to write after ``OUTPUT_PATH=`` and to record in the
        summary's ``output_path`` field. Empty string is returned only on
        the catastrophic path where an exception fired before the
        destination could be resolved (e.g., a network failure during the
        first fetch); pipeline consumers see ``OUTPUT_PATH=`` (no value)
        as a signal that no CSV exists at any path.
    """
    if output_path == STDOUT_SENTINEL:
        return STDOUT_SENTINEL
    # Normalize to an absolute path. ``Path.resolve(strict=False)`` works even
    # if the file does not exist yet (e.g., the path was resolved but the
    # write itself raised before completing).
    if resolved_file_path is None:
        return ""
    return str(Path(resolved_file_path).resolve())


def _emit_run_tail(
    *,
    json_summary: bool,
    summary: dict[str, Any],
    output_label: str,
    csv_on_stdout: bool,
) -> None:
    """Emit the `OUTPUT_PATH=` line and (optionally) the JSON summary.

    Single chokepoint for the two trailing-output concerns so the ordering
    rule from spec §5.3 is encoded in exactly one place:

      1. ``OUTPUT_PATH=<label>`` always to **stderr**, regardless of any
         other flag. Independent of ``--quiet`` and ``--json-summary``
         because pipeline integrators need it on every run.
      2. If ``--json-summary`` is set, the summary JSON line lands on
         **stdout** by default but on **stderr** when CSV bytes own stdout
         (``--output -``). Always emitted *after* the ``OUTPUT_PATH=`` line
         when both share the stderr stream.

    Args:
        json_summary: Whether ``--json-summary`` was set.
        summary: Pre-built summary dict matching the §5.3.4 schema.
        output_label: The string to put after ``OUTPUT_PATH=``.
        csv_on_stdout: ``True`` when ``--output -`` claimed stdout; routes
            the summary to stderr in that case so stdout stays pure CSV.
    """
    # ``OUTPUT_PATH=`` always goes to stderr — independent of ``--quiet``
    # (pipelines need it even in quiet mode) and independent of
    # ``--json-summary`` (both can coexist; this line comes first on
    # stderr when both share that stream). Spec §5.3.3.
    print(f"{OUTPUT_PATH_LINE_PREFIX}{output_label}", file=sys.stderr, flush=True)

    if not json_summary:
        return

    # ``separators`` removes the spaces pandas/json normally inserts between
    # ``key`` and ``value`` and between successive items so the line stays
    # compact and stable across Python versions. One-line JSON keeps the
    # ``tail -n1 stream | jq .`` integration point trivial.
    summary_line = json.dumps(summary, separators=(",", ":"))
    summary_stream = sys.stderr if csv_on_stdout else sys.stdout
    print(summary_line, file=summary_stream, flush=True)


def _build_summary(
    *,
    config_filters: tuple,
    scrape_link: str,
    output_label: str,
    row_count: int,
    query_url: str,
    started_at: datetime.datetime,
    exit_code: int,
) -> dict[str, Any]:
    """Construct the §5.3.4 summary dict.

    Captures ``finished_at`` at call time so ``duration_ms`` reflects the
    full run including any post-write logging. ``filters`` is the resolved
    ``{key: value}`` dict for filter-driven runs and ``None`` for
    ``--scrape-link`` (spec §5.3.4 row 6: ``object | null``; no filter
    resolution happens on the scrape-link path).
    """
    finished_at = datetime.datetime.now(tz=datetime.UTC)
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)

    # Build the ``filters`` payload. ``config.filters`` is a tuple of
    # ``(key, value)`` pairs after ``json_to_tuples``; for the
    # ``--scrape-link`` path no filter resolution happened, so emit ``null``.
    filters_payload: dict[str, str] | None = None if scrape_link else dict(config_filters)

    return {
        "schema_version": JSON_SUMMARY_SCHEMA_VERSION,
        "exit_code": exit_code,
        "output_path": output_label,
        "row_count": row_count,
        "query_url": query_url,
        "filters": filters_payload,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_ms": duration_ms,
    }


def run_stock_screener(
    history: bool = False,
    debug: bool = False,
    scrape_link: str = "",
    filters: str = "",
    output_path: str = "",
    quiet: bool = False,
    json_summary: bool = False,
) -> None:
    """Run the screener pipeline end-to-end and exit with a classified code.

    Owns the four pillars (see module docstring). Does not return a code —
    instead emits the trailing OUTPUT_PATH/JSON-summary chokepoint and
    calls ``sys.exit(<classified code>)`` so the CLI surface stays
    ``-> None``. ``CliRunner.invoke`` translates the ``SystemExit`` back
    into ``result.exit_code`` for tests.

    Args:
        history: Reuse the most recent filter selection.
        debug: Lower the logger level to DEBUG.
        scrape_link: Direct Finviz URL; bypasses query construction.
        filters: Canonical-shape JSON string of filters (the CLI normalizes
            ``--filter`` / ``--filters-json`` / ``--filters-file`` into
            this single string).
        output_path: CSV destination (file path or the ``-`` stdout
            sentinel); empty string defers to env / default.
        quiet: Suppress human chatter (INFO/DEBUG console).
        json_summary: Emit a single-line JSON summary at end of run.
    """
    # Captured before any side effect so ``duration_ms`` reflects the full run.
    # ISO-8601 UTC at function entry per spec §5.3.4 row 7. Use a tz-aware
    # ``datetime`` so the serialized timestamp carries the ``+00:00`` suffix.
    started_at = datetime.datetime.now(tz=datetime.UTC)

    logger.set_level(logging.DEBUG if debug else logging.INFO)
    # ``--quiet`` mutes INFO/DEBUG on the two console handlers (spec §5.3.1).
    # Decoupled from level on purpose so ``--debug --quiet`` still writes
    # debug records to ``logs/activity.log`` via the file handlers — only
    # the console emit is short-circuited.
    logger.set_quiet(quiet)

    config = configurator.build_config(
        use_history=history,
        scrape_link=scrape_link,
        filters=filters,
        output_path=output_path,
    )
    # When `--output -` is set, the CSV stream owns stdout. Reroute the two
    # human-readable console handlers to stderr so progress / banner / typing
    # chatter doesn't corrupt the CSV bytes piped to a downstream consumer.
    # File handlers (activity.log, error.log) are unaffected. Spec §5.2 + §5.3.
    csv_on_stdout = config.output_path == STDOUT_SENTINEL
    if csv_on_stdout:
        logger.set_console_stream(sys.stderr)
    logger.debug(f"Config: {config}", "Config created successfully:")

    # Direct-URL bypass: when a scrape link is supplied, skip the interactive filter
    # picker + query builder entirely and use the URL verbatim as the screener query.
    quarry = config.scrape_link or select_filters_and_values(config)
    logger.debug(f"Quarry: {quarry}", "Quarry created successfully:")

    # Track these locals so the trailing emission chokepoint can populate
    # the summary regardless of which branch the run took. ``resolved_file_path``
    # stays ``None`` for the stdout-streaming path so the output_label
    # resolver returns the ``-`` sentinel verbatim; it also stays ``None``
    # if an exception fires before the destination is resolved (the
    # output_label then resolves to the empty string, signaling to pipeline
    # consumers that no CSV exists).
    row_count = 0
    resolved_file_path: str | None = None
    # Default exit code is SUCCESS; the classifier in the except branch
    # overwrites this when an exception fires. Pinned via the named
    # constant so a future renumbering in `exit_codes` propagates here
    # without an edit.
    code = exit_codes.SUCCESS

    try:
        logger.info(f"Fetching HTML content from {quarry}", "Fetching HTML - Started")
        html_content = fetch_page_sync(quarry)
        logger.info(f"HTML content fetched from {quarry} successfully", "Fetching HTML - Completed")

        stock_screener_page = StockTableScreeningContent(html_content)

        pages = fetch_urls(quarry, stock_screener_page.page_count)
        data_rows = aggregate_rows(pages)

        # Pillar 2 dispatch decision lives at the orchestrator boundary so
        # the CSV write site can hand pandas a path *or* ``sys.stdout``
        # uniformly. Pre-resolve `resolved_file_path` here so it's also
        # available for the zero-row branch below (which needs to write a
        # header-only file at the same destination).
        if not csv_on_stdout:
            resolved_file_path = config.file_path("stock_screener")

        # ``aggregate_rows`` returns a list-of-lists: one inner list per
        # matched ``<table>``, each containing zero-or-more row tuples.
        # Empty inner lists are legal (the screener table exists but its
        # ``<tbody>`` is empty), so "zero rows" means *every* inner list
        # is empty, not "data_rows itself is empty". The flatten + len
        # check is the single source of truth for the zero-row branch
        # selector.
        flattened_row_count = sum(len(rows) for rows in data_rows)

        if flattened_row_count == 0:
            # Zero-row success path (spec §5.4 last two bullets). Every
            # successful run must produce a discoverable output, so write a
            # header-only CSV (or stream the header line) and exit 0. This
            # closes the Pillar-4 honesty gap where today's silent return
            # left ``OUTPUT_PATH=`` empty even though exit was 0.
            logger.warn(
                "No data was found for the given filters; writing header-only CSV.",
                title="Data Handling --->",
            )
            empty_df = _build_empty_data_frame(stream_to_stdout=csv_on_stdout)
            if csv_on_stdout:
                empty_df.to_csv(sys.stdout, index=False)
                logger.info("Header-only CSV streamed to stdout", "Data Handling --->")
            else:
                empty_df.to_csv(resolved_file_path, index=False)
                logger.info(
                    f"Header-only CSV saved to {resolved_file_path}",
                    "Data Handling --->",
                )
            # row_count stays 0 — summary will reflect the zero-row result.
        else:
            # Happy path — at least one ticker row. The `stream_to_stdout`
            # toggle controls the `Ticker` carve-out: stdout writes raw
            # symbol; file destinations keep the Excel `=HYPERLINK(...)`
            # wrap. Spec §5.6.
            final_df = build_data_frame(data_rows, stream_to_stdout=csv_on_stdout)
            logger.info("Data frame created successfully", "Data Handling --->")
            logger.info("Saving data frame to csv file", "Data Handling --->")
            if csv_on_stdout:
                final_df.to_csv(sys.stdout, index=False)
                logger.info("CSV streamed to stdout", "Data Handling --->")
            else:
                final_df.to_csv(resolved_file_path, index=False)
                logger.info(f"File saved to {resolved_file_path}", "Data Handling --->")
            # Row count excludes the header. ``len(final_df)`` is the number
            # of data rows in the written CSV. Spec §5.3.4 row 4.
            row_count = len(final_df)
    except Exception as exc:
        # Pillar 4 classifier. Map the exception to a documented exit code
        # so a downstream pipeline can branch on the cause without
        # parsing the traceback. Spec §5.4. The traceback itself is
        # surfaced via `logger.error` (error.log) — we do not swallow it.
        code = exit_codes.classify(exc)
        # `Logger.error` has a flipped signature relative to the other
        # methods: `(title, message="")` instead of `(message, title="")`.
        # The pre-existing footgun is documented in the spec §15 nuance;
        # call it in the documented order so the title color + message
        # surface correctly. Includes the classified code name so the
        # error log line is self-explanatory without cross-referencing
        # the exit code separately.
        logger.error(
            f"Pipeline failed with {type(exc).__name__} -> exit {code} ({_exit_code_name(code)})",
            message=f"{exc} (see logs/error.log for traceback)",
        )

    # Trailing emission chokepoint. Runs on both the success and the
    # except path so pipeline integrators get the `OUTPUT_PATH=` line and
    # (optionally) the JSON summary on every invocation — even when the
    # exit code is non-zero. Spec §5.3.3 / §5.3.4 / §5.4.
    output_label = _resolve_output_path_label(config.output_path, resolved_file_path)
    summary = _build_summary(
        config_filters=config.filters,
        scrape_link=config.scrape_link,
        output_label=output_label,
        row_count=row_count,
        query_url=quarry,
        started_at=started_at,
        exit_code=code,
    )
    _emit_run_tail(
        json_summary=json_summary,
        summary=summary,
        output_label=output_label,
        csv_on_stdout=csv_on_stdout,
    )
    # Restore the singleton logger to its default-quiet state so this
    # function leaves no in-process residue for the next caller (matters
    # most for ``CliRunner``-based tests that may invoke the entry point
    # repeatedly inside one Python process).
    logger.set_quiet(False)

    # Single exit point. SUCCESS is the no-exception path; the except
    # branch above overwrote `code` with the classified value for any
    # other outcome. `sys.exit(0)` is a no-op for normal CLI invocation
    # and a friendly close for `CliRunner.invoke` (which surfaces the
    # value via `result.exit_code`).
    sys.exit(code)


def _exit_code_name(code: int) -> str:
    """Return the human-readable name of an exit code for log messages.

    Tiny helper kept private; the `exit_codes` module owns the constants
    and the classifier, this owns only the human-facing label.
    """
    return {
        exit_codes.SUCCESS: "SUCCESS",
        exit_codes.INTERNAL: "INTERNAL",
        exit_codes.USAGE: "USAGE",
        exit_codes.UPSTREAM: "UPSTREAM",
        exit_codes.DATA: "DATA",
    }.get(code, f"UNKNOWN({code})")
