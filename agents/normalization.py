"""Normalization helpers for currency and dates used in ingestion and extraction."""
from __future__ import annotations

import datetime
from typing import Optional


def normalize_currency_code(code: Optional[str]) -> Optional[str]:
    """Normalize currency codes to uppercase 3-letter strings."""
    if not code:
        return None
    code = code.strip().upper()
    if len(code) != 3:
        return None
    return code


def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """Normalize date strings to YYYY-MM-DD; return None on failure."""
    if not date_str:
        return None
    try:
        # accept YYYY or YYYY-MM-DD
        if len(date_str) == 4:
            return f"{date_str}-01-01"
        parsed = datetime.date.fromisoformat(date_str)
        return parsed.isoformat()
    except Exception:
        return None
