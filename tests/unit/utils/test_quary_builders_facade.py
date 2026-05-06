from __future__ import annotations

from finpack.utils.quary_builders import build_stock_screener_query


def test_build_stock_screener_query_basic():
    # Use known keys from params modules
    filters = [("fa_pe", "u15"), ("ta_sma50", "pa")]
    url = build_stock_screener_query(filters)
    assert url.startswith("https://finviz.com/screener.ashx?")
    # Must include both filters joined with commas
    assert "f=fa_pe_u15,ta_sma50_pa" in url
