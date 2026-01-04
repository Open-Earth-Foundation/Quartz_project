"""Funding/date filter node to enforce 20-year funded scope before review."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import config
from agent_state import AgentState
from agents.funding_scope import gate_project_scope
from agents.normalization import normalize_date

logger = logging.getLogger(__name__)


def _coerce_date(project: Dict[str, Any], field: str) -> None:
    value = project.get(field)
    normalized = normalize_date(value) if isinstance(value, str) or value is None else None
    if normalized:
        project[field] = normalized


def _apply_gate(project: Dict[str, Any], years: int, accepted_statuses: List[str]) -> Tuple[bool, Dict[str, Any]]:
    status = project.get("ProjectStatus")
    start = project.get("StartDate")
    end = project.get("EndDate")
    gate = gate_project_scope(status, start, end, years=years, accepted_statuses=accepted_statuses)
    return gate["in_scope"], gate


def filter_projects_by_scope(
    projects: List[Dict[str, Any]],
    years: int,
    accepted_statuses: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []

    for project in projects:
        _coerce_date(project, "StartDate")
        _coerce_date(project, "EndDate")
        in_scope, gate = _apply_gate(project, years, accepted_statuses)
        project_with_gate = {**project, "_gate": gate}
        if in_scope:
            kept.append(project_with_gate)
        else:
            dropped.append(project_with_gate)
    return kept, dropped


def funding_filter_node(state: AgentState) -> AgentState:
    """LangGraph node: filter funded_projects by funding/date gate and log decisions."""
    current = state.funded_projects or []
    accepted_statuses = list(config.ACCEPTED_FUNDED_STATUSES)
    lookback_years = state.metadata.get("funded_lookback_years", config.FUNDED_LOOKBACK_YEARS)

    kept, dropped = filter_projects_by_scope(current, lookback_years, accepted_statuses)
    # Evidence validation: ensure SourceUrl present; log missing for follow-up
    missing_evidence = [p for p in kept if not ((p.get("Traceability") or {}).get("SourceUrl") if isinstance(p.get("Traceability"), dict) else None)]
    filter_log = {
        "total_candidates": len(current),
        "kept": len(kept),
        "dropped": len(dropped),
        "missing_evidence": len(missing_evidence),
        "accepted_statuses": accepted_statuses,
        "lookback_years": lookback_years,
    }
    if config.ENABLE_FUNDING_FILTER_LOG:
        logger.info(f"Funding filter applied: {filter_log}")
        if dropped:
            sample_reasons = [d.get("_gate", {}).get("reason") for d in dropped[:3]]
            logger.info(f"Examples of dropped projects: {sample_reasons}")

    # Update state copies
    state.funded_projects = kept
    state.funding_filter_log.extend(dropped)
    state.decision_log.append(
        {
            "agent": "FundingFilter",
            "action": "filter_applied",
            "kept": len(kept),
            "dropped": len(dropped),
            "missing_evidence": len(missing_evidence),
            "lookback_years": lookback_years,
        }
    )
    return state
