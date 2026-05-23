"""GET /filters integration — real adapter + real fincli inventory walk.

Drives the route handler through the actual ``get_filter_inventory``
adapter and the real ``list_valid_filters_with_labels`` walker in
``fincli.resource.params.validators``. No HTTP is involved at any layer —
the inventory is pure Python introspection — so no mocking is needed.

Pins the spec §5.6 byte-equivalence claim: ``GET /filters`` and the CLI's
``fincli --list-filters --json`` must return the same key set because
both transports call the same underlying function.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from fincli.resource.params.validators import list_valid_filters_with_labels


def test_get_filters_real_data_returns_full_inventory(client: TestClient) -> None:
    """End-to-end GET /filters returns the full param-class inventory.

    Cross-checks the response against the function the adapter wraps so a
    future drift between the route, the adapter, and the underlying walker
    fails loudly — and so the test does not silently rot if the inventory
    grows or shrinks.
    """
    response = client.get("/filters")

    assert response.status_code == 200
    body = response.json()

    # Schema version is pinned at 1 (spec §4.4 / CONTRACTS §7).
    assert body["schema_version"] == 1

    # The ``keys`` array is the canonical iteration order — Go's map decode
    # randomizes ``filters`` map order, so polyglot consumers iterate
    # ``keys``. Source-of-truth comparison: same set, same order.
    expected_inventory = list_valid_filters_with_labels()
    assert body["keys"] == list(expected_inventory.keys())

    # Every key has a matching entry in the filters map with label + values.
    assert set(body["filters"].keys()) == set(expected_inventory.keys())
    for key, expected_entry in expected_inventory.items():
        entry = body["filters"][key]
        assert entry["label"] == expected_entry["label"]
        assert entry["values"] == expected_entry["values"]


def test_get_filters_inventory_count_matches_param_classes(client: TestClient) -> None:
    """GET /filters returns the full param-class inventory count.

    Sanity check that the walker found entries across all three registered
    param classes (Fundamental / Descriptive / Technical). A regression that
    drops one class entirely (e.g. by breaking the ``_iter_param_entries``
    introspection rules) would collapse this count drastically.
    """
    response = client.get("/filters")
    assert response.status_code == 200
    body = response.json()

    # Source of truth = the walker the adapter calls. If the inventory
    # grows or shrinks, this number tracks automatically; we just pin the
    # invariant "non-trivial inventory" so an empty result fails loudly.
    expected_count = len(list_valid_filters_with_labels())
    assert len(body["keys"]) == expected_count
    assert expected_count >= 60, (
        f"Inventory unexpectedly small ({expected_count} keys); "
        "expected ~66 across Fundamental/Descriptive/Technical."
    )
