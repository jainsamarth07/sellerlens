"""Shared helpers for settlement-report parsing."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

# Match Indian / international currency formatting: ₹1,23,456.78 / -Rs. 5,000 / (1,200)
_CURRENCY_RE = re.compile(r"[^\d\.\-]")


def to_float(value: Any, default: float = 0.0) -> float:
    """Coerce a value to float, tolerating currency symbols, commas, and NaN."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return default
        return float(value)

    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "-", "n/a", "na"}:
        return default

    # Accounting-style negatives: (1,234.56) → -1234.56
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]

    cleaned = _CURRENCY_RE.sub("", s)
    if cleaned in {"", "-", "."}:
        return default
    try:
        result = float(cleaned)
    except ValueError:
        return default
    return -result if negative else result


def to_int(value: Any, default: int = 0) -> int:
    """Coerce a value to int, tolerating floats and NaN."""
    f = to_float(value, default=float(default))
    try:
        return int(f)
    except (ValueError, OverflowError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Return a stripped string, treating NaN / None as empty."""
    if value is None:
        return default
    if isinstance(value, float) and np.isnan(value):
        return default
    s = str(value).strip()
    return s if s else default


def normalise_label(label: Any) -> str:
    """Lower-case and collapse whitespace/punctuation in a row label."""
    if label is None:
        return ""
    s = str(label).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


# Strings that Flipkart appends to column headers but are not part of the field name.
_RS_SUFFIX_RE = re.compile(r"\s*\(\s*rs\.?\s*\)\s*", re.IGNORECASE)
_FORMULA_RE = re.compile(r"\s*[\n\r=\[].*$", re.DOTALL)
_PLACEHOLDER_RE = re.compile(r"^\s*(#gid=|#ref|=|#name)", re.IGNORECASE)


def clean_column_name(name: Any) -> str:
    """Strip Flipkart's currency suffix and trailing formula annotations from a header.

    Examples:
        'Sale Amount (Rs.)'                    → 'Sale Amount'
        'Marketplace Fee (Rs.)\\n= SUM (V:AI)' → 'Marketplace Fee'
        ' Payment Date '                       → 'Payment Date'
    """
    if name is None:
        return ""
    s = str(name)
    s = _FORMULA_RE.sub("", s)        # drop everything from \n / = / [ onward
    s = _RS_SUFFIX_RE.sub("", s)      # strip "(Rs.)" / "(Rs)" anywhere
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_placeholder_value(value: Any) -> bool:
    """True if *value* is a Google-Sheets cross-sheet reference / unresolved formula."""
    if not isinstance(value, str):
        return False
    return bool(_PLACEHOLDER_RE.match(value.strip()))


def find_column(df: pd.DataFrame, *candidates: str) -> str | None:
    """Return the first column in *df* that matches one of *candidates* (case-insensitive).

    Matches against cleaned & normalised column names so that headers like
    'Sale Amount (Rs.)' or 'Marketplace Fee (Rs.)\\n= SUM(V:AI)' resolve cleanly.
    Exact (cleaned) matches win; otherwise the shortest containing match wins.
    """
    if df is None or df.empty:
        return None
    # Map normalised-cleaned-name → original column (preserve column order)
    norm_map: dict[str, str] = {}
    for col in df.columns:
        key = normalise_label(clean_column_name(col))
        if key and key not in norm_map:
            norm_map[key] = col
    for cand in candidates:
        key = normalise_label(cand)
        if not key:
            continue
        if key in norm_map:
            return norm_map[key]
        # Partial match: prefer the shortest matching column name (most specific).
        partial = [(nk, orig) for nk, orig in norm_map.items() if key in nk]
        if partial:
            partial.sort(key=lambda kv: len(kv[0]))
            return partial[0][1]
    return None
