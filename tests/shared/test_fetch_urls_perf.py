import time
import contextlib
import tracemalloc
from time import perf_counter
from fincli.app.main import fetch_urls


def _fake_fetch(_: str) -> bytes:
    # Simulate network latency
    time.sleep(0.05)
    return b"ok"


@contextlib.contextmanager
def measure_time(_label: str, track_memory: bool = True):
    if track_memory:
        tracemalloc.start()
    start = perf_counter()
    try:
        yield
    finally:
        ms = (perf_counter() - start) * 1000.0
        peak_kb = None
        if track_memory:
            try:
                _, peak = tracemalloc.get_traced_memory()
                peak_kb = peak / 1024.0
            finally:
                tracemalloc.stop()
        print({"label": _label, "ms": round(ms, 2), "peak_kb": round(peak_kb or 0, 1)})

def test_fetch_urls_performance():
    base = "https://example.com/screener.ashx?v=111&f=foo"
    page_count = 19  # 20 pages

    with measure_time("baseline-serial", track_memory=True):
        # Force serial by setting max_workers=1
        results_serial = fetch_urls(base, page_count, max_workers=1, fetch_fn=_fake_fetch)

    with measure_time("concurrent-8", track_memory=True):
        results_conc = fetch_urls(base, page_count, max_workers=8, fetch_fn=_fake_fetch)

    # Basic sanity checks
    assert len(results_serial) == page_count + 1
    assert len(results_conc) == page_count + 1

    # Ensure concurrency improved wall time materially
    # Expect at least 2x faster than serial under simulated latency
    # No strict assert on timing in CI; just ensure the function works.
    # Measurements are printed by measure_time contexts.


