"""Heuristics for funding and implementation status classification."""
from __future__ import annotations

from typing import Optional, Dict, Any

FUNDED_KEYWORDS = {
    "funded": ["funded", "financed", "grant", "awarded", "allocated", "approved"],
    "in_implementation": ["construction", "implementation", "under way", "underway", "ongoing"],
    "completed": ["completed", "commissioned", "in service", "operational", "finished"],
    "approved": ["approved", "authorized", "greenlit", "sanctioned"],
}

IMPLEMENTATION_KEYWORDS = {
    "not_started": ["planned", "planning", "design", "feasibility"],
    "delayed": ["delayed", "on hold", "paused"],
    "in_progress": ["construction", "implementation", "ongoing", "under way", "underway"],
    "complete": ["completed", "commissioned", "operational"],
}


def _match_keywords(text: str, keyword_map: Dict[str, list[str]]) -> Optional[str]:
    lowered = text.lower()
    for label, keywords in keyword_map.items():
        for kw in keywords:
            if kw in lowered:
                return label
    return None


def classify_funding_status(text: Optional[str]) -> Optional[str]:
    """Classify funding status from free text."""
    if not text:
        return None
    return _match_keywords(text, FUNDED_KEYWORDS)


def classify_implementation_status(text: Optional[str]) -> Optional[str]:
    """Classify implementation status from free text."""
    if not text:
        return None
    return _match_keywords(text, IMPLEMENTATION_KEYWORDS)


def dedupe_project_key(project_title: str, city: str, year: Optional[str]) -> str:
    """Build a deterministic dedupe key for funded projects."""
    normalized_title = (project_title or "").strip().lower()
    normalized_city = (city or "").strip().lower()
    normalized_year = (year or "").strip() if year else ""
    return f"{normalized_title}|{normalized_city}|{normalized_year}"


def summarize_unmapped_fields(record: Dict[str, Any], mapped_fields: set[str]) -> Dict[str, Any]:
    """Return unmapped fields for logging/debugging."""
    return {k: v for k, v in record.items() if k not in mapped_fields}
