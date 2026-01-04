"""Staged extraction orchestration for funded city climate projects."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False
    OpenAI = None

import config
from agent_state import AgentState
from agents import extraction_flow
from agents.search_or_scrape import search_or_scrape
from agents.funding_scope import gate_project_scope

logger = logging.getLogger(__name__)

STAGE_INSTRUCTIONS = {
    "stage1": "Extract ProjectTitle, ProjectStatus, StartDate, EndDate, Location (city/region/country), Traceability.SourceUrl. Return a funded/implemented yes/no/unknown hint.",
    "stage2": "Extract Financing.* (currency, amount) and Funders.*. Keep nulls if absent. Do not drop previously extracted fields.",
    "stage3": "Extract TechnicalDescriptors.* and Impact.*. Keep nulls if absent. Preserve finance/funder fields.",
    "stage4": "Check for missing critical fields and propose follow-up search query. Do not fabricate data.",
}


def _llm_extract_stage(
    stage_name: str,
    document: Dict[str, Any],
    partial_project: Dict[str, Any],
) -> Dict[str, Any]:
    """Call LLM for a single stage. Returns dict of fields to merge."""
    if not OPENAI_AVAILABLE or not config.OPENROUTER_API_KEY:
        return {}

    content = document.get("content") or document.get("markdown") or ""
    if not content:
        return {}

    client = OpenAI(
        base_url=config.OPENROUTER_BASE_URL,
        api_key=config.OPENROUTER_API_KEY,
        default_headers={"HTTP-Referer": config.HTTP_REFERER, "X-Title": config.SITE_NAME},
    )

    user_prompt = (
        f"You are filling stage '{stage_name}' of a staged extractor for funded city climate projects. "
        f"{STAGE_INSTRUCTIONS.get(stage_name, '')} "
        "Always return JSON with only the fields you can confidently fill; unknown values should be null."
    )
    try:
        response = client.chat.completions.create(
            model=config.STRUCTURED_MODEL,
            messages=[
                {"role": "system", "content": "Return compact JSON only. Do not include prose."},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "stage": stage_name,
                            "document_url": document.get("url"),
                            "known_partial_project": partial_project,
                            "content_snippet": content[:4000],
                        },
                        ensure_ascii=False,
                    ),
                },
                {"role": "assistant", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=config.DEFAULT_TEMPERATURE,
        )
        raw = response.choices[0].message.content or "{}"
        cleaned = raw.strip()
        if cleaned.startswith("```json") and cleaned.endswith("```"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = cleaned[3:-3].strip()
        return json.loads(cleaned)
    except Exception as exc:
        logger.warning(f"Stage {stage_name} extraction failed; returning partial. Error: {exc}")
        return {}


def _heuristic_stage1(document: Dict[str, Any]) -> Dict[str, Any]:
    """Cheap fallback extraction for stage 1."""
    return {
        "ProjectTitle": document.get("title") or document.get("metadata", {}).get("title"),
        "Traceability": {"SourceUrl": document.get("url")} if document.get("url") else None,
        "ProjectStatus": document.get("status") or None,
        "Location": document.get("metadata", {}).get("location") if isinstance(document.get("metadata"), dict) else None,
    }


def run_staged_extraction_on_document(
    document: Dict[str, Any],
    lookback_years: int,
    accepted_statuses: List[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Dict[str, Any]]:
    """Return (final_project_or_None, followup_request_or_None, gate_info)."""
    partial = extraction_flow.init_partial_project()
    evidence_log: List[Dict[str, Any]] = []

    stage1_data = _llm_extract_stage("stage1", document, partial) or _heuristic_stage1(document)
    partial = extraction_flow.merge_partial(partial, stage1_data)
    gate_raw = gate_project_scope(
        partial.get("ProjectStatus"),
        partial.get("StartDate"),
        partial.get("EndDate"),
        years=lookback_years,
        accepted_statuses=accepted_statuses,
    )
    gate_info = {
        "in_scope": gate_raw["in_scope"],
        "reason": gate_raw["reason"],
        "anchor_date": gate_raw["anchor_date"],
        "funding_rule": gate_raw.get("funding_rule", extraction_flow.FUNDING_RULE_TEXT if hasattr(extraction_flow, "FUNDING_RULE_TEXT") else None),
        "candidate": partial,
    }
    evidence_log.append({"stage": "stage1", "data": stage1_data, "gate": gate_info})
    if not gate_info.get("in_scope", False):
        return None, None, gate_info

    stage2_data = _llm_extract_stage("stage2", document, partial)
    if stage2_data:
        partial = extraction_flow.merge_partial(partial, stage2_data)
        evidence_log.append({"stage": "stage2", "data": stage2_data})

    stage3_data = _llm_extract_stage("stage3", document, partial)
    if stage3_data:
        partial = extraction_flow.merge_partial(partial, stage3_data)
        evidence_log.append({"stage": "stage3", "data": stage3_data})

    missing = extraction_flow.collect_missing_fields(partial, extraction_flow.CRITICAL_FINAL_FIELDS)
    followup_request: Optional[Dict[str, Any]] = None
    if missing:
        followup_request = extraction_flow.build_followup_request(partial)
        evidence_log.append({"stage": "stage4", "missing": missing, "followup": followup_request})
        # Include constructed query for visibility
        followup_request = search_or_scrape("", missing, followup_request.get("known_context", {}))

    partial["_evidence_log"] = evidence_log
    return partial, followup_request, gate_info


def run_staged_extraction_over_scrapes(state: AgentState) -> AgentState:
    """Process scraped_data or selected_for_extraction and populate funded_projects."""
    target_docs: List[Dict[str, Any]] = []
    if state.selected_for_extraction:
        selected_urls = set(state.selected_for_extraction)
        target_docs = [d for d in state.scraped_data if d.get("url") in selected_urls]
    else:
        target_docs = list(state.scraped_data)

    lookback_years = state.metadata.get("funded_lookback_years", config.FUNDED_LOOKBACK_YEARS)
    accepted_statuses = list(config.ACCEPTED_FUNDED_STATUSES)

    funded_projects: List[Dict[str, Any]] = list(state.funded_projects)
    followups: List[Dict[str, Any]] = list(state.funded_followups)

    for doc in target_docs:
        project, followup, gate_info = run_staged_extraction_on_document(doc, lookback_years, accepted_statuses)
        if project:
            funded_projects.append(project)
        if followup:
            followups.append({"url": doc.get("url"), **followup})
        state.evidence_log.append({"url": doc.get("url"), "gate": gate_info})

    state.funded_projects = funded_projects
    state.funded_followups = followups
    state.decision_log.append(
        {
            "agent": "StagedExtractor",
            "action": "extraction_completed",
            "funded_projects_found": len(funded_projects),
            "followups_needed": len(followups),
        }
    )
    return state
