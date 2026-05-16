"""Unified entry point for parsing settlement reports from any supported platform."""

from __future__ import annotations

from typing import Any

from backend.processors.amazon_parser import parse_amazon_settlement
from backend.processors.flipkart_parser import parse_flipkart_settlement


def parse_settlement(
    file_bytes: bytes,
    filename: str,
    platform: str | None = None,
) -> dict[str, Any]:
    """Auto-detect platform and dispatch to the correct parser.

    Args:
        file_bytes: The raw uploaded file contents.
        filename: Original filename — used for extension-based detection.
        platform: Optional explicit platform ("flipkart" or "amazon").

    Returns:
        The canonical analytics dict (see flipkart_parser for shape).
    """
    name = (filename or "").lower()
    plat = (platform or "").lower()

    if plat == "amazon" or name.endswith(".csv"):
        return parse_amazon_settlement(file_bytes)
    return parse_flipkart_settlement(file_bytes)
