"""Funding scope helpers for Quartz city climate projects.

Used to keep a single definition of what counts as in-scope: funded/implemented
status plus a default 20-year lookback window. Stage 1 extraction can call
`gate_project_scope` to decide whether to proceed with deeper extraction.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional, Tuple

import config

# Text token for prompts to keep definition consistent
FUNDING_RULE_TEXT = (
    "In scope if the project shows municipal or third-party funding commitment or is marked implemented "
    f"and has a start/end decision within the last {config.FUNDED_LOOKBACK_YEARS} years. "
    f"Accepted statuses: {', '.join(config.ACCEPTED_FUNDED_STATUSES)}."
)

# Minimal fields we try to capture in Stage 1 before deciding to continue
GATE_REQUIRED_FIELDS = [
    "ProjectTitle",
    "ProjectStatus",
    "StartDate",
    "EndDate",
    "Location",
    "Traceability",
]


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse YYYY-MM-DD; return None on failures."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


def lookback_start(years: int = config.FUNDED_LOOKBACK_YEARS) -> date:
    """Compute the start date for the lookback window."""
    today = date.today()
    return date(today.year - years, today.month, today.day)


def status_is_funded(
    status: Optional[str],
    accepted_statuses: Iterable[str] = tuple(config.ACCEPTED_FUNDED_STATUSES),
) -> bool:
    """Check whether a status string matches accepted funded/implemented values."""
    if not status:
        return False
    normalized = status.strip().lower()
    return normalized in {s.lower() for s in accepted_statuses}


def date_is_in_window(start: Optional[str], end: Optional[str], years: int) -> Tuple[bool, Optional[date]]:
    """Return whether any project date is within window plus the chosen anchor date."""
    anchor = lookback_start(years)
    start_dt = _parse_date(start)
    end_dt = _parse_date(end)

    # Prefer start date, fall back to end date
    candidate = start_dt or end_dt
    if not candidate:
        return False, None
    return candidate >= anchor, candidate


def gate_project_scope(
    status: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    years: int = config.FUNDED_LOOKBACK_YEARS,
    accepted_statuses: Iterable[str] = tuple(config.ACCEPTED_FUNDED_STATUSES),
) -> Dict[str, Any]:
    """Decide if a project is likely in-scope (funded/implemented within lookback).

    Returns a dict with:
      - in_scope: bool
      - reason: short text explaining the decision
      - anchor_date: parsed date used for window comparison (or None)
    """
    funded = status_is_funded(status, accepted_statuses)
    within_window, anchor_date = date_is_in_window(start_date, end_date, years)

    if funded and within_window:
        return {"in_scope": True, "reason": "funded_status_and_recent_date", "anchor_date": anchor_date}
    if not funded and within_window:
        return {"in_scope": False, "reason": "recent_date_but_status_not_funded", "anchor_date": anchor_date}
    if funded and not within_window:
        return {"in_scope": False, "reason": "funded_status_but_too_old", "anchor_date": anchor_date}
    return {"in_scope": False, "reason": "insufficient_data_for_gate", "anchor_date": anchor_date}
