"""Search/scrape follow-up helper for Stage 4 gap closure.

This module exposes a simple callable that can be wired as a tool/function call.
It builds a query using known context and missing fields, leaving execution to
the caller (e.g., researcher node or external search service).
"""
from __future__ import annotations

from typing import Dict, List


def build_followup_query(known_context: Dict[str, str], needed_fields: List[str]) -> str:
    """Create a compact search query string to find missing funded-project fields."""
    parts = []
    title = known_context.get("title")
    city = known_context.get("city")
    country = known_context.get("country")
    status = known_context.get("status")
    year = None
    for key in ("start_date", "end_date"):
        if known_context.get(key):
            year = known_context[key][:4]
            break

    if title:
        parts.append(title)
    if city:
        parts.append(city)
    if country:
        parts.append(country)
    if year:
        parts.append(year)
    if status:
        parts.append(status)

    # Emphasize funding evidence in query
    parts.append("funding grant budget bond implemented climate project")
    parts.append(" ".join(sorted(set(needed_fields))))

    return " ".join([p for p in parts if p])


def search_or_scrape(query: str, needed_fields: List[str], known_context: Dict[str, str]) -> Dict[str, object]:
    """Placeholder callable to be wired as a tool; returns the intended query and context."""
    constructed_query = build_followup_query(known_context, needed_fields)
    return {
        "query": query or constructed_query,
        "constructed_query": constructed_query,
        "needed_fields": needed_fields,
        "known_context": known_context,
    }
