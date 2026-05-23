"""Adapters bridging the Fin CLI API surface to fincli's Python internals.

``adapters/fincli.py`` is the only file in ``fincli_api/`` allowed to
import from ``fincli/`` (architectural rule per spec §3.2). The two
exported functions are the bridge points the FastAPI route handlers
call to fulfil ``GET /filters`` and ``POST /screens`` respectively.
"""

from fincli_api.adapters.fincli import get_filter_inventory, run_screen

__all__ = ["get_filter_inventory", "run_screen"]
