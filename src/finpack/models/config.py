"""Core configuration models for finpack.

The new library exposes explicit configuration objects that allow callers to
control providers, concurrency, caching, and logging without relying on global
side effects. This module defines the canonical data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass(slots=True)
class ProviderConfig:
    """Configuration for a single data provider."""

    name: str
    priority: int = 1
    api_key: Optional[str] = None
    enabled: bool = True
    # TODO: Extend with provider-specific options (e.g., endpoints, throttling)


@dataclass(slots=True)
class CacheConfig:
    """Configuration for caching behaviour."""

    enabled: bool = True
    ttl_seconds: int = 3600
    backend: str = "memory"
    directory: Optional[Path] = None
    # TODO: Add redis connection details when implementing distributed cache


@dataclass(slots=True)
class RuntimeConfig:
    """Runtime configuration covering concurrency and timeouts."""

    max_concurrent_requests: int = 8
    request_timeout_seconds: int = 30
    retry_attempts: int = 2
    retry_backoff_seconds: float = 0.5


@dataclass(slots=True)
class FinPackConfig:
    """Top-level configuration consumed by :class:`finpack.core.session.Session`."""

    providers: List[ProviderConfig] = field(default_factory=list)
    cache: CacheConfig = field(default_factory=CacheConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    def get_primary_provider(self) -> Optional[ProviderConfig]:
        """Return the highest priority enabled provider, if any."""

        enabled = [provider for provider in self.providers if provider.enabled]
        if not enabled:
            return None
        return sorted(enabled, key=lambda provider: provider.priority)[0]

