"""Differentiated exit codes for the screener pipeline (Pillar 4).

Per `docs/features/archive/pipeline-mode-spec.md` §5.4, ``run_stock_screener`` maps
unhandled exceptions to one of five exit codes so a downstream pipeline can
distinguish "found nothing" from "network failed" from "Finviz changed its
HTML" without having to parse the traceback.

Five-code table (single source of truth — `CONTRACTS.md` §1 mirrors these):

  * ``SUCCESS``   = 0 — Run completed; CSV written (or streamed). Includes
    zero-row results: a zero-row run still writes a header-only CSV so the
    "every successful run produces a discoverable output" contract holds.
  * ``INTERNAL``  = 1 — Uncaught exception that escaped the orchestrator
    (default for anything ``classify`` does not recognize). Traceback is
    surfaced to stderr and ``logs/error.log``.
  * ``USAGE``     = 2 — Click's default for ``UsageError`` and
    ``BadParameter``. Click owns this code; the orchestrator does not emit it
    directly. Includes the mutual-exclusion error (Pillar 1) and unknown
    filter key/value errors raised by ``validate_filter_pairs``.
  * ``UPSTREAM``  = 3 — ``cfscrape`` raised, an HTTP error, a DNS failure,
    or a request timeout. Classified by checking
    ``requests.exceptions.RequestException`` (cfscrape's exceptions are
    ``requests`` subclasses).
  * ``DATA``      = 4 — Data-contract / parse failure: the screener
    ``<table>`` element is missing, BeautifulSoup couldn't parse the page,
    or a column is missing where one was expected. Classified by checking
    ``IndexError``, ``AttributeError``, ``KeyError`` — the three exception
    types BS4-based row parsing raises when the HTML shape drifts.

Tests import the constants from here so a future renumbering touches one
file. Hardcoding the integers in test bodies would re-create the
silent-corruption hazard the spec was written to close.
"""

from __future__ import annotations

import requests

# Exit-code constants — pinned values per spec §5.4. Renumbering any of these
# is a breaking change governed by `CONTRACTS.md` §7 (CLI exit-code
# convention is part of the stable surface).
SUCCESS = 0
INTERNAL = 1
USAGE = 2
UPSTREAM = 3
DATA = 4


def classify(exc: BaseException) -> int:
    """Map an exception instance to its exit code per spec §5.4.

    The classifier is deliberately narrow: it recognises only the two
    well-understood failure families (upstream HTTP/network errors and
    HTML-parse errors) and falls back to ``INTERNAL`` for everything else
    rather than guessing. Surprises should crash visibly with a traceback,
    not be silently absorbed into ``UPSTREAM`` or ``DATA``.

    Args:
        exc: The exception caught at the orchestrator boundary. Must be a
            ``BaseException`` (the orchestrator uses ``except Exception``
            so ``KeyboardInterrupt`` / ``SystemExit`` are not classified
            here and continue to propagate).

    Returns:
        One of ``UPSTREAM``, ``DATA``, or ``INTERNAL``. The other two
        constants (``SUCCESS``, ``USAGE``) are never produced by this
        function: ``SUCCESS`` is the no-exception path, and ``USAGE`` is
        emitted by Click before any code reaches the orchestrator.
    """
    # Upstream / network failures. ``requests.exceptions.RequestException``
    # is the umbrella base class for ConnectionError, Timeout, HTTPError,
    # and the broader request-lifecycle errors; ``cfscrape``'s wrapper
    # raises ``requests`` subclasses internally, so this single isinstance
    # check captures both libraries' failure surface.
    if isinstance(exc, requests.exceptions.RequestException):
        return UPSTREAM

    # Data-contract / parse failures. BS4 row parsing raises one of these
    # three when the HTML shape drifts: ``IndexError`` on ``cells[1]`` when
    # a row is short, ``AttributeError`` on ``.find('a').get('href')`` when
    # the link cell is missing, ``KeyError`` on a missing dict lookup
    # downstream. The orchestrator re-raises these from the BS4 invocation
    # site so they reach the classifier unmodified.
    if isinstance(exc, (IndexError, AttributeError, KeyError)):
        return DATA

    # Anything else — ValueError from a column-count mismatch, a third-party
    # library exception, a bug in our own code — is "uncaught internal"
    # and bubbles as exit 1 with the original traceback. The traceback is
    # what makes the root cause debuggable; classifying everything would
    # hide it behind a code without the cause.
    return INTERNAL
