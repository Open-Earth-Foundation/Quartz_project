"""Staged extraction scaffolding for extract_funded_project.

Provides minimal utilities to:
- initialize a partial project object with nulls
- run a lightweight Stage 1 gate
- merge stage outputs while preserving prior evidence
- detect critical missing fields and request search/scrape follow-ups
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

import config
from agents.funding_scope import FUNDING_RULE_TEXT, gate_project_scope

# Critical fields required to consider a project "accepted" for deeper extraction
CRITICAL_STAGE1_FIELDS = [
    "ProjectTitle",
    "ProjectStatus",
    "StartDate",
    "EndDate",
    "Location",
    "Traceability",
]

CRITICAL_FINAL_FIELDS = [
    "ProjectTitle",
    "ProjectStatus",
    "Location",
    "Traceability",
    "Financing",
    "Funders",
]


def init_partial_project() -> Dict[str, Any]:
    """Return a blank partial project with nulls for all top-level fields."""
    return {
        "ProjectTitle": None,
        "ProjectSummary": None,
        "ProjectStatus": None,
        "StartDate": None,
        "EndDate": None,
        "Location": None,
        "TechnicalDescriptors": None,
        "Impact": None,
        "Financing": None,
        "Funders": None,
        "Traceability": None,
    }


def run_stage1_gate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Run lightweight gate to decide if deeper extraction is warranted."""
    status = candidate.get("ProjectStatus")
    start_date = candidate.get("StartDate")
    end_date = candidate.get("EndDate")
    gate_result = gate_project_scope(status, start_date, end_date)
    return {
        "in_scope": gate_result["in_scope"],
        "reason": gate_result["reason"],
        "anchor_date": gate_result["anchor_date"],
        "funding_rule": FUNDING_RULE_TEXT,
        "candidate": candidate,
    }


def merge_partial(base: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Merge new stage output into base, keeping prior values unless new has data."""
    merged = deepcopy(base)
    for key, value in new.items():
        if value is None:
            continue
        # If both are dicts, shallow merge
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def collect_missing_fields(project: Dict[str, Any], required: List[str]) -> List[str]:
    """Identify which required fields are still null/empty."""
    missing = []
    for field in required:
        val = project.get(field)
        if val is None or val == "" or val == []:
            missing.append(field)
    return missing


def should_trigger_followup(project: Dict[str, Any]) -> bool:
    """Check if critical final fields are missing and need search/scrape."""
    missing = collect_missing_fields(project, CRITICAL_FINAL_FIELDS)
    return len(missing) > 0


def build_followup_request(project: Dict[str, Any]) -> Dict[str, Any]:
    """Return a structured follow-up request to feed a search/scrape tool."""
    missing = collect_missing_fields(project, CRITICAL_FINAL_FIELDS)
    context = {
        "title": project.get("ProjectTitle"),
        "city": (project.get("Location") or {}).get("CityName") if isinstance(project.get("Location"), dict) else None,
        "country": (project.get("Location") or {}).get("Country") if isinstance(project.get("Location"), dict) else None,
        "status": project.get("ProjectStatus"),
        "start_date": project.get("StartDate"),
        "end_date": project.get("EndDate"),
    }
    return {
        "needed_fields": missing,
        "known_context": context,
        "query_hint": f"Funded/implemented city climate project within {config.FUNDED_LOOKBACK_YEARS} years",
    }
