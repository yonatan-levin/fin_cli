"""
Lightweight measurement utilities for timing and memory usage.

Usage:
    from shared.infrastructure.utils.measure import measure_time

    with measure_time("fetch_urls baseline") as m:
        fetch_urls(...)
    print(m.ms)
"""

from __future__ import annotations

import contextlib
import time
import tracemalloc
from dataclasses import dataclass
from typing import Optional, Iterator


@dataclass
class MeasureResult:
    label: str
    ms: float
    peak_kb: Optional[float]


class _Measure:
    def __init__(self, label: str, track_memory: bool = True) -> None:
        self.label = label
        self.track_memory = track_memory
        self._start: float = 0.0
        self._stop: float = 0.0
        self.ms: float = 0.0
        self.peak_kb: Optional[float] = None

    def __enter__(self) -> "_Measure":
        if self.track_memory:
            tracemalloc.start()
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop = time.perf_counter()
        self.ms = (self._stop - self._start) * 1000.0
        if self.track_memory:
            try:
                _, peak = tracemalloc.get_traced_memory()
                self.peak_kb = peak / 1024.0
            finally:
                tracemalloc.stop()


@contextlib.contextmanager
def measure_time(label: str, track_memory: bool = True) -> Iterator[_Measure]:
    m = _Measure(label=label, track_memory=track_memory)
    try:
        m.__enter__()
        yield m
    finally:
        m.__exit__(None, None, None)


