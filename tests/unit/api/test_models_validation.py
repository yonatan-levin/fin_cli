"""Light edge-case tests for Pydantic models (T2 NIT carryforwards).

Scope is intentionally narrow — pin the CURRENT behavior so future model
constraint changes (T2 REVIEWER NIT defer) flag as regressions. This
file does NOT add Field constraints; that is a separate spec.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fincli_api.models import ErrorResponse, Stock


def test_stock_serialization_matches_spec_example(sample_stock: Stock) -> None:
    """Round-trip ``model_dump_json -> model_validate`` preserves the wire shape.

    Pins spec §4.3 ``Stock`` example: every field survives a JSON
    round-trip with identical values and types. Catches accidental
    serializer customization (e.g. alias drift) that would break
    polyglot consumers.
    """
    rebuilt = Stock.model_validate_json(sample_stock.model_dump_json())

    assert rebuilt == sample_stock
    # Spot-check the snake_case wire fields (vs. PascalCase Finviz cols)
    # since the snake_case rule is the spec §4.3 normalization contract.
    dumped = rebuilt.model_dump()
    assert "market_cap" in dumped
    assert "finviz_url" in dumped
    assert "rank" in dumped


def test_error_response_rejects_invalid_error_class() -> None:
    """Literal discriminator on ``error_class`` rejects out-of-set values.

    Spec §5.2 fixes the four legal classes (``validation`` / ``upstream``
    / ``parsing`` / ``internal``). The Literal enforces this at parse
    time so a route handler cannot accidentally widen the envelope.
    """
    with pytest.raises(ValidationError):
        ErrorResponse(error_class="not_a_real_class", message="x")  # type: ignore[arg-type]
