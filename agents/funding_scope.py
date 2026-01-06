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
    "In scope if the project shows evidence of funding commitment OR is marked as implemented/started/approved. "
    "Specific dates and amounts are optional. Priority given to projects with at least a project title and status. "
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
    """Decide if a project is likely in-scope (funded/implemented).

    RELAXED REQUIREMENTS: Accept projects if they have:
    - A project status (any status suggesting project exists)
    - No strict date requirements needed
    - Funding or implementation hints are strong signals but not required

    Returns a dict with:
      - in_scope: bool
      - reason: short text explaining the decision
      - anchor_date: parsed date used for window comparison (or None)
    """
    funded = status_is_funded(status, accepted_statuses)
    within_window, anchor_date = date_is_in_window(start_date, end_date, years)

    # RELAXED: Accept if status suggests project is funded/implemented (regardless of dates)
    if funded:
        return {"in_scope": True, "reason": "funded_or_implemented_status", "anchor_date": anchor_date}
    
    # RELAXED: Accept any project with status that's not explicitly negative
    # (e.g., "planned", "proposed", "approved", etc all suggest something real)
    if status and isinstance(status, str):
        status_lower = status.lower().strip()
        # Reject only if status explicitly says "rejected", "cancelled", "failed", "abandoned"
        if any(reject_word in status_lower for reject_word in ["rejected", "cancelled", "canceled", "failed", "abandoned", "unknown"]):
            return {"in_scope": False, "reason": "negative_or_unknown_status", "anchor_date": anchor_date}
        # Accept anything else that has a status
        return {"in_scope": True, "reason": "project_status_exists_relaxed", "anchor_date": anchor_date}
    
    # If no status at all, insufficient data
    return {"in_scope": False, "reason": "no_project_status", "anchor_date": anchor_date}
