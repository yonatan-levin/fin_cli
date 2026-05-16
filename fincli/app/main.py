import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from config.config import STDOUT_SENTINEL
from core.configuration import configurator
from fincli.stock_screening.content.stock_table import StockTableScreeningContent
from fincli.cli.cli_stock_screener import select_filters_and_values
from logger.logger import logger
from fincli.stock_screening.locators.stock_table_locators import StockTableLocators
from fincli.utils.market_cap import convert_market_cap_to_numeric
from fincli.utils.web_scraper import fetch_page_sync

# Pillar 3 JSON summary contract (`docs/features/pipeline-mode-spec.md` §5.3.4).
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


def build_data_frame(data_rows):
    df = pd.concat([pd.DataFrame(row) for row in data_rows])
    df.columns = StockTableLocators.PD_TABLE_COLUMNS
    # Coerce the Market Cap column into a nullable Float64 array so unparseable
    # cells render as empty CSV cells rather than the literal strings "nan",
    # "<NA>", or 0.0. Contract: docs/features/pipeline-mode-spec.md §5.5 +
    # CONTRACTS.md §3.1.
    df["Market Cap"] = pd.array(
        [convert_market_cap_to_numeric(v) for v in df["Market Cap"]],
        dtype="Float64",
    )
    df["Symbol"] = df["Ticker"]
    df["Ticker"] = '=HYPERLINK("' + df["Link"] + '", "' + df["Ticker"] + '")'
    df.drop(columns=["Link"], axis=1, inplace=True)
    return df


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
            ``Config.file_path`` result), or ``None`` when streaming.

    Returns:
        The string to write after ``OUTPUT_PATH=`` and to record in the
        summary's ``output_path`` field.
    """
    if output_path == STDOUT_SENTINEL:
        return STDOUT_SENTINEL
    # Normalize to an absolute path. ``Path.resolve(strict=False)`` works even
    # if the file does not exist yet (we may be reporting the path for the
    # zero-row code path which currently exits before writing — Task 6
    # backfills the header-only CSV write).
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
    finished_at = datetime.datetime.now(tz=datetime.timezone.utc)
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)

    # Build the ``filters`` payload. ``config.filters`` is a tuple of
    # ``(key, value)`` pairs after ``json_to_tuples``; for the
    # ``--scrape-link`` path no filter resolution happened, so emit ``null``.
    filters_payload: dict[str, str] | None
    if scrape_link:
        filters_payload = None
    else:
        filters_payload = dict(config_filters)

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
    # Captured before any side effect so ``duration_ms`` reflects the full run.
    # ISO-8601 UTC at function entry per spec §5.3.4 row 7. Use a tz-aware
    # ``datetime`` so the serialized timestamp carries the ``+00:00`` suffix.
    started_at = datetime.datetime.now(tz=datetime.timezone.utc)

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
    # the summary regardless of which branch the run took (zero-row early
    # return vs. successful write). ``resolved_file_path`` stays ``None``
    # for the stdout-streaming path so the output_label resolver returns
    # the ``-`` sentinel verbatim.
    row_count = 0
    resolved_file_path: str | None = None

    try:
        logger.info(f"Fetching HTML content from {quarry}", "Fetching HTML - Started")
        html_content = fetch_page_sync(quarry)
        logger.info(f"HTML content fetched from {quarry} successfully", "Fetching HTML - Completed")

        stock_screener_page = StockTableScreeningContent(html_content)

        pages = fetch_urls(quarry, stock_screener_page.page_count)
        data_rows = aggregate_rows(pages)

        if len(data_rows) == 0:
            logger.error("Data Handling --->", "No data was found for the given filters")
            # Falls through to the ``finally`` block so the trailing
            # ``OUTPUT_PATH=`` + summary emission still fires. ``row_count``
            # stays 0; ``resolved_file_path`` stays ``None``. Spec §5.3.4
            # row 4 (row_count is 0 for empty result). Task 6 will rewrite
            # this branch to write a header-only CSV; for Task 5 the
            # summary is still emitted so pipeline integrators get a
            # well-formed handle even on the zero-row path.
            return

        final_df = build_data_frame(data_rows)
        logger.info("Data frame created successfully", "Data Handling --->")
        logger.info("Saving data frame to csv file", "Data Handling --->")
        # Pillar-2 destination dispatch. The `-` sentinel means "stream CSV to
        # stdout"; pandas accepts a file-like object, so handing it `sys.stdout`
        # writes the CSV bytes directly (and nothing else, since the logger has
        # already been rerouted to stderr above). Otherwise resolve the path
        # through `config.file_path` so the precedence chain
        # (--output PATH > FINCLI_OUTPUT_DIR > default) is honored at one site.
        if csv_on_stdout:
            final_df.to_csv(sys.stdout, index=False)
            logger.info("CSV streamed to stdout", "Data Handling --->")
        else:
            resolved_file_path = config.file_path("stock_screener")
            final_df.to_csv(resolved_file_path, index=False)
            logger.info(f"File saved to {resolved_file_path}", "Data Handling --->")
        # Row count excludes the header. ``len(final_df)`` is the number of
        # data rows in the written CSV. Spec §5.3.4 row 4.
        row_count = len(final_df)
    finally:
        # Single chokepoint for the trailing OUTPUT_PATH + summary emission.
        # Lives in ``finally`` so the zero-row early-return path also surfaces
        # a discovery line for the downstream pipeline. ``exit_code`` is
        # pinned to 0 here: Pillar 4 (Task 6) introduces classified non-zero
        # codes; for Task 5 a successful return from this function means a
        # successful run, and any uncaught exception will be raised through
        # ``finally`` (Click will set the exit code, and the summary will not
        # be emitted because the exception propagates before
        # ``_emit_run_tail`` finishes).
        output_label = _resolve_output_path_label(config.output_path, resolved_file_path)
        summary = _build_summary(
            config_filters=config.filters,
            scrape_link=config.scrape_link,
            output_label=output_label,
            row_count=row_count,
            query_url=quarry,
            started_at=started_at,
            exit_code=0,
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
