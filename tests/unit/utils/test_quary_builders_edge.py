from __future__ import annotations

from finpack.utils.quary_builders import build_stock_screener_query


def test_build_stock_screener_query_ignores_unknown_keys():
    filters = [("fa_pe", "u15"), ("unknown_key", "val")]
    url = build_stock_screener_query(filters)
    assert "fa_pe_u15" in url
    assert "unknown_key" not in url


def test_build_stock_screener_query_empty():
    url = build_stock_screener_query([])
    assert url.endswith("&f=&ft=2")
