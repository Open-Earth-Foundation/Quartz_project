"""
Agent 1: Query Formulation & Strategic Planner
"""

import logging
import os
from typing import Dict, List, Any, Optional
import re  # Import regex for parsing
from dataclasses import asdict  # Import asdict for AgentState conversion
import json  # Import json at the top level
from datetime import datetime
from pathlib import Path  # Import Path

# Add tenacity import
import tenacity  # Corrected import
from pydantic import ValidationError  # Changed from pydantic_core

# Setup logging early so it's available for import errors
logger = logging.getLogger(__name__)

# Try importing OpenAI and set flag
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None  # Define OpenAI as None if import fails
    logger.warning(
        "OpenAI library not found. Planner LLM calls will be skipped or use fallback."
    )

# Need os imported for PROMPT_FILE_PATH
import os

# Correct imports: AgentState from agent_state, SearchPlanSchema from agents.schemas
from agent_state import AgentState, create_initial_state  # type: ignore
from agents.schemas import SearchPlanSchema, SearchQuery  # Import schemas
from agents.utils.country_language_map import (
    get_primary_language,
)  # Import language mapping utility

import config  # type: ignore


# Use pathlib for robust path handling
PROMPT_DIR = Path(__file__).parent / "prompts"
# PLANNER_PROMPT_PATH = PROMPT_DIR / "agent1_planner.md" # REMOVED

# REMOVED load_planner_prompt_template function and its global invocation


async def planner_node(state: AgentState) -> AgentState:
    """Generates a research plan based on the initial prompt and country context."""
    logger.info(
        f"PLANNER_NODE: Entered. Current iteration: {state.current_iteration}, Target Country: {state.target_country}, Sector: {state.target_sector}"
    )
    # REMOVED check for PLANNER_PROMPT_TEMPLATE

    # --- MODIFIED: Increment iteration count on a dictionary copy that will be used throughout --- #
    current_state_dict = asdict(state)  # Work with dict copy
    current_state_dict["current_iteration"] = state.current_iteration + 1
    current_state_dict["decision_log"] = list(state.decision_log)
    user_content = ""

    # Reset consecutive deep dive count since planner represents a non-deep_dive action
    current_state_dict["consecutive_deep_dive_count"] = 0
    logger.info(
        "Resetting consecutive_deep_dive_count to 0 since planner node is being called (non-deep_dive action)"
    )

    logger.info(
        f"Starting iteration {current_state_dict['current_iteration']} for sector {state.target_sector}..."
    )

    if not OPENAI_AVAILABLE or not config.OPENROUTER_API_KEY:
        msg = (
            "OpenAI library not installed."
            if not OPENAI_AVAILABLE
            else "OpenRouter API key not configured."
        )
        logger.error(f"{msg} Planner node cannot function fully.")
        current_state_dict["decision_log"].append(
            {"agent": "Planner", "action": "error", "message": msg}
        )
        if not OPENAI_AVAILABLE:
            current_search_plan = list(current_state_dict.get("search_plan", []))
            current_search_plan.append(
                {
                    "query": f"{state.target_country} GHGI data",
                    "language": "en",
                    "priority": "high",
                    "status": "pending",
                    "target_type": "generic_fallback_no_openai",
                }
            )
            current_state_dict["search_plan"] = current_search_plan
        return AgentState(**current_state_dict)

    # --- Load Planner Prompt based on Mode and Sector --- #
    research_mode = state.metadata.get("research_mode", "country")
    search_mode = getattr(
        state, "search_mode", "ghgi_data"
    )  # NEW: Check for search_mode

    logger.info(f"Planner Mode - Research: {research_mode}, Search: {search_mode}")

    if research_mode == "city":
        # City mode - use city-specific prompt, or city+sector combined prompt
        if not state.target_city:
            logger.error(
                "City mode specified but target_city is not set. Aborting planner."
            )
            current_state_dict["decision_log"].append(
                {
                    "agent": "Planner",
                    "action": "error_early_exit",
                    "message": "City mode specified but target_city not set.",
                }
            )
            return AgentState(**current_state_dict)

        # NEW: Check for search_mode and sector for city mode
        if search_mode == "funded_projects":
            # Use sector-specific funded projects city prompt if available
            if state.target_sector:
                sector = state.target_sector.lower()
                city_funded_sector_prompt_path = (
                    PROMPT_DIR / f"funded_{sector}_city.md"
                )
                if city_funded_sector_prompt_path.exists():
                    base_prompt_path = city_funded_sector_prompt_path
                    logger.info(f"Using sector-specific funded projects city prompt: {base_prompt_path}")
                else:
                    # Fallback to generic funded projects city prompt
                    base_prompt_path = PROMPT_DIR / "funded_projects_city.md"
                    logger.info(f"Sector-specific funded city prompt not found, using generic: {base_prompt_path}")
            else:
                # Use generic funded projects city prompt
                base_prompt_path = PROMPT_DIR / "funded_projects_city.md"
                logger.info(f"Using generic funded projects city prompt: {base_prompt_path}")
        elif state.target_sector:
            # Use sector-specific city prompt: {sector}_city.md
            city_sector_prompt_path = (
                PROMPT_DIR / f"{state.target_sector.lower()}_city.md"
            )
            if city_sector_prompt_path.exists():
                base_prompt_path = city_sector_prompt_path
                logger.info(f"Using city+sector specific prompt: {base_prompt_path}")
            else:
                # Fallback to generic city prompt
                base_prompt_path = PROMPT_DIR / "agent1_planner_city.md"
                logger.info(
                    f"City+sector prompt not found, using generic city prompt: {base_prompt_path}"
                )
                logger.warning(
                    f"Consider creating {city_sector_prompt_path} for better city+sector integration"
                )
        else:
            # City-only mode
            base_prompt_path = PROMPT_DIR / "agent1_planner_city.md"
            logger.info(f"Using city-only prompt: {base_prompt_path}")

        placeholder = "{city_name_from_AgentState}"
        target_name = state.target_city

    elif research_mode == "region":
        region_name = (
            state.target_region
            or state.metadata.get("region_name")
            or state.target_country
        )
        if not region_name:
            logger.error(
                "Region mode specified but no region name is available. Aborting planner."
            )
            current_state_dict["decision_log"].append(
                {
                    "agent": "Planner",
                    "action": "error_early_exit",
                    "message": "Region mode specified but region name missing.",
                }
            )
            return AgentState(**current_state_dict)

        sector = state.target_sector.lower() if state.target_sector else ""
        if not sector:
            logger.error(
                "Target sector is not specified for region mode. Aborting planner."
            )
            current_state_dict["decision_log"].append(
                {
                    "agent": "Planner",
                    "action": "error_early_exit",
                    "message": "Target sector not specified for region mode.",
                }
            )
            return AgentState(**current_state_dict)

        region_key = region_name.strip().lower()
        if region_key in ("european union", "eu"):
            base_prompt_path = PROMPT_DIR / "agent1_planner_region_eu.md"
            placeholder = "{region_name_from_AgentState}"
            logger.info(f"Using EU region planner prompt: {base_prompt_path}")
        else:
            base_prompt_path = PROMPT_DIR / "agent1_planner.md"
            placeholder = "{country_name_from_AgentState}"
            logger.warning(
                f"No region-specific prompt found for '{region_name}'. Falling back to default country prompt."
            )

        target_name = region_name

    else:
        # Country mode - existing logic but with search_mode support
        # NEW: Check for funded_projects search mode first
        if search_mode == "funded_projects":
            # Use sector-specific funded projects country prompt if available
            if state.target_sector:
                sector = state.target_sector.lower()
                country_funded_sector_prompt_path = (
                    PROMPT_DIR / f"funded_{sector}_country.md"
                )
                if country_funded_sector_prompt_path.exists():
                    base_prompt_path = country_funded_sector_prompt_path
                    logger.info(f"Using sector-specific funded projects country prompt: {base_prompt_path}")
                else:
                    # Fallback to generic funded projects country prompt
                    base_prompt_path = PROMPT_DIR / "funded_projects_country.md"
                    logger.info(f"Sector-specific funded country prompt not found, using generic: {base_prompt_path}")
            else:
                # Use generic funded projects country prompt
                base_prompt_path = PROMPT_DIR / "funded_projects_country.md"
                logger.info(f"Using generic funded projects country prompt: {base_prompt_path}")
            placeholder = "{country_name_from_AgentState}"
            target_name = state.target_country
        else:
            # Original GHGI data mode logic
            sector = state.target_sector.lower() if state.target_sector else ""
            if not sector:
                logger.error(
                    "Target sector is not specified. Cannot determine planner prompt. Aborting planner."
                )
                current_state_dict["decision_log"].append(
                    {
                        "agent": "Planner",
                        "action": "error_early_exit",
                        "message": "Target sector not specified.",
                    }
                )
                return AgentState(**current_state_dict)

            # Check if English-only mode is enabled
            english_only_mode = state.metadata.get("english_only_mode", False)

            if english_only_mode:
                # Use the English-only version of the planner prompt
                base_prompt_path = PROMPT_DIR / "agent1_planner_english.md"
                logger.info(f"Using English-only planner prompt: {base_prompt_path}")
            else:
                # Use the sector-specific prompt (original behavior)
                base_prompt_path = PROMPT_DIR / f"{sector}.md"
                logger.info(f"Using sector-specific planner prompt: {base_prompt_path}")

            placeholder = "{country_name_from_AgentState}"
            target_name = state.target_country

    prompt_template = ""  # Initialize prompt_template

    try:
        prompt_template = base_prompt_path.read_text(encoding="utf-8")
        logger.info(f"Successfully loaded planner prompt from: {base_prompt_path}")
    except FileNotFoundError:
        logger.error(f"Planner prompt file not found: {base_prompt_path}")
        # Return state, decision log will be updated in the next check
    except Exception as e:
        logger.error(f"Error loading planner prompt file {base_prompt_path}: {e}")
        # Return state, decision log will be updated in the next check
    # --- END Load Prompt --- #

    if not target_name or not prompt_template:
        msg = (
            f"Target {research_mode} missing."
            if not target_name
            else "Failed to load prompt template."
        )
        logger.error(f"{msg} Aborting planner.")
        current_state_dict["decision_log"].append(
            {"agent": "Planner", "action": "error_early_exit", "message": msg}
        )
        return AgentState(**current_state_dict)

    if placeholder not in prompt_template:
        logger.error(f"Placeholder '{placeholder}' not found. Aborting planner.")
        current_state_dict["decision_log"].append(
            {
                "agent": "Planner",
                "action": "error",
                "message": f"Placeholder '{placeholder}' missing.",
            }
        )
        return AgentState(**current_state_dict)

    # --- Prompt formatting and splitting (adapt if prompts change structure) --- #
    full_user_content = prompt_template.replace(placeholder, target_name)

    # Replace optional placeholders if present
    # Get primary language from metadata or infer from country name
    primary_langs = state.metadata.get("primary_languages", [])
    if primary_langs:
        primary_language = primary_langs[0]
    else:
        # If metadata doesn't have primary languages yet, infer from country name
        if research_mode == "country" and state.target_country:
            primary_language = get_primary_language(state.target_country)
        else:
            primary_language = "English"

    optional_replacements = {
        "{sector_name_from_AgentState}": state.target_sector or "all sectors",
        "{region_name_from_AgentState}": (
            (state.target_region or state.metadata.get("region_name") or target_name)
            if research_mode == "region"
            else None
        ),
        "{country_name_from_AgentState}": state.target_country,
        "{city_name_from_AgentState}": state.target_city,
        "{primary_language_from_AgentState}": primary_language,
    }
    for token, value in optional_replacements.items():
        if token in full_user_content and value:
            full_user_content = full_user_content.replace(token, value)

    # Log the complete combined prompt for debugging
    logger.info(f"=== COMBINED PROMPT DEBUG ===")
    logger.info(f"Research Mode: {research_mode}")
    logger.info(f"Target: {target_name}")
    logger.info(f"Sector: {state.target_sector}")
    logger.info(f"Placeholder used: {placeholder}")
    logger.info(f"Prompt file used: {base_prompt_path}")
    logger.info(f"Total prompt length: {len(prompt_template)} chars")

    # Log a substantial portion of the actual prompt being sent
    logger.info(f"=== ACTUAL PROMPT CONTENT (first 1000 chars) ===")
    logger.info(full_user_content[:1000])
    logger.info(f"=== ACTUAL PROMPT CONTENT (last 500 chars) ===")
    logger.info(full_user_content[-500:])
    logger.info(f"=== END PROMPT DEBUG ===")

    # NEW: Initialize system_msg_base here for use later
    system_msg = "You are an expert research assistant tasked with formulating a research plan for Greenhouse Gas Inventory (GHGI) data."
    user_content = full_user_content  # Initialize with default value

    lines = full_user_content.split("\n", 1)
    if len(lines) > 0 and "System Prompt:" in lines[0]:
        system_msg = lines[0].replace("System Prompt:", "").strip()
        if len(lines) > 1:
            user_content = lines[1].strip()
    # --- END Prompt formatting --- #

    llm_raw_output: str = ""
    structured_output_str: str = ""
    try:
        if not OpenAI:
            raise ImportError("OpenAI class is not available due to import failure.")

        client = OpenAI(
            base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY
        )

        # NEW: Generate appropriate system message based on search_mode
        if search_mode == "funded_projects":
            system_msg_base = "You are an expert research assistant tasked with formulating a research plan to discover funded climate projects."
        elif research_mode == "city":
            system_msg_base = "You are an expert research assistant tasked with formulating a city-specific research plan for Greenhouse Gas Inventory (GHGI) data."
        else:
            system_msg_base = "You are an expert research assistant tasked with formulating a sector-specific research plan for Greenhouse Gas Inventory (GHGI) data."

        if research_mode == "city":
            logger.info(
                f"Sending initial planning prompt to {config.THINKING_MODEL} for city: {state.target_city}"
            )
        elif research_mode == "region":
            logger.info(
                f"Sending initial planning prompt to {config.THINKING_MODEL} for region: {target_name}"
            )
        else:
            logger.info(
                f"Sending initial planning prompt to {config.THINKING_MODEL} for country: {state.target_country}"
            )
        logger.debug(
            f"Planner User Content Snippet for THINKING_MODEL: {user_content[:200]}..."
        )

        response_raw_text = client.chat.completions.create(
            model=config.THINKING_MODEL,
            messages=[
                {"role": "system", "content": system_msg_base},
                {"role": "user", "content": user_content},
            ],
            temperature=config.DEFAULT_TEMPERATURE,
        )

        llm_raw_output = (
            (response_raw_text.choices[0].message.content or "")
            if response_raw_text and response_raw_text.choices
            else ""
        )
        logger.debug(
            f"Raw LLM Output from {config.THINKING_MODEL}:\n{llm_raw_output[:500]}..."
        )

        if llm_raw_output:
            try:
                log_dir = os.path.join(os.getcwd(), "logs", "planner_outputs")
                os.makedirs(log_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if research_mode == "city":
                    target_name_sanitized = re.sub(
                        r"[^\w\-_]", "_", state.target_city or "UnknownCity"
                    )
                    filename = f"planner_output_raw_city_{target_name_sanitized}_{timestamp}.md"
                elif research_mode == "region":
                    target_name_sanitized = re.sub(
                        r"[^\w\-_]", "_", target_name or "UnknownRegion"
                    )
                    filename = f"planner_output_raw_region_{target_name_sanitized}_{timestamp}.md"
                else:
                    target_name_sanitized = re.sub(
                        r"[^\w\-_]", "_", state.target_country or "UnknownCountry"
                    )
                    filename = (
                        f"planner_output_raw_{target_name_sanitized}_{timestamp}.md"
                    )
                filepath = os.path.join(log_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(llm_raw_output)
                logger.info(f"Saved raw planner LLM output to: {filepath}")
            except Exception as e:
                logger.error(f"Failed to save raw planner LLM output: {e}")

        if not llm_raw_output:
            logger.warning(f"{config.THINKING_MODEL} returned empty response.")
            current_state_dict["decision_log"].append(
                {
                    "agent": "Planner",
                    "action": "warning",
                    "message": f"{config.THINKING_MODEL} returned empty response.",
                }
            )
            current_search_plan_fallback = list(
                current_state_dict.get("search_plan", [])
            )
            if research_mode == "city":
                current_search_plan_fallback.append(
                    {
                        "query": f"{state.target_city} greenhouse gas emissions data",
                        "language": "en",
                        "priority": "high",
                        "status": "pending",
                        "target_type": "fallback_generic_city",
                    }
                )
            elif research_mode == "region":
                current_search_plan_fallback.append(
                    {
                        "query": f"{target_name} greenhouse gas inventory data",
                        "language": "en",
                        "priority": "high",
                        "status": "pending",
                        "target_type": "fallback_generic_region",
                    }
                )
            else:
                current_search_plan_fallback.append(
                    {
                        "query": f"{state.target_country} greenhouse gas inventory data",
                        "language": "en",
                        "priority": "high",
                        "status": "pending",
                        "target_type": "fallback_generic",
                    }
                )
            current_state_dict["search_plan"] = current_search_plan_fallback
            logger.info(
                f"PLANNER_NODE: Returning from empty LLM response. Iteration: {current_state_dict.get('current_iteration')}"
            )
            return AgentState(**current_state_dict)

        # --- Second LLM call for structured output ---
        logger.info(
            f"Sending raw text to {config.STRUCTURED_MODEL} for structured extraction."
        )
        extraction_system_prompt = (
            "You are an expert data extraction assistant. Your task is to analyze a research plan and convert it to structured JSON format. "
            "CRITICAL: Each search query object MUST have these required fields:\n"
            "  - 'query' (string): The ACTUAL search phrase/text that a researcher would type (e.g., 'Lime application emissions Chile regional data')\n"
            "  - 'language' (string): ISO 639-1 language code ('en' for English, 'es' for Spanish, etc.)\n"
            "  - 'priority' (string): 'high', 'medium', or 'low'\n"
            "  - 'rank' (integer): Sequential number starting from 1, based on importance/execution order\n"
            "  - 'target_type' (string): e.g., 'primary_ghgi', 'statistical_yearbook', 'generic'\n\n"
            "EXAMPLE of correct search_query object:\n"
            "{\n"
            "  'query': 'Lime application emissions Chile regional data',\n"
            "  'language': 'en',\n"
            "  'priority': 'high',\n"
            "  'rank': 1,\n"
            "  'target_type': 'primary_ghgi'\n"
            "}\n\n"
            "The output MUST be a valid JSON object with:\n"
            "  - 'search_queries': list of search query objects (REQUIRED)\n"
            "  - 'target_country_locode': 2-letter country code if available\n"
            "  - 'primary_languages': list of language names if available\n"
            "  - Other optional top-level fields if their information is present in the text\n"
            "Do NOT include optional fields if the information is not explicitly in the text."
        )
        extraction_user_prompt = (
            f"Extract all search phrases from the research plan below and convert them to a JSON object. "
            f"IMPORTANT: The 'query' field MUST contain the complete search phrase text as it appears in the plan, "
            f"NOT an identifier or ID. Assign sequential ranks starting from 1. "
            f"Infer 'language' from the search phrase (English phrases get 'en', Spanish phrases get 'es', etc.). "
            f"Infer 'priority' based on importance/specificity (more specific/relevant = higher priority). "
            f"Infer 'target_type' based on the phrase content.\n\n"
            f"Research Plan Text:\n---\n{llm_raw_output}\n---"
        )

        parsed_plan_data: Optional[SearchPlanSchema] = None
        structured_output_str = ""

        def should_retry_planner(exception):
            return isinstance(
                exception,
                (
                    TypeError,
                    AttributeError,
                    IndexError,
                    json.JSONDecodeError,
                    ValidationError,
                ),
            )

        try:

            @tenacity.retry(
                stop=tenacity.stop_after_attempt(3),
                wait=tenacity.wait_fixed(2),
                retry=tenacity.retry_if_exception(should_retry_planner),
                before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
                reraise=True,
            )
            def attempt_structured_extraction():
                nonlocal structured_output_str, parsed_plan_data

                response_structured = None
                try:
                    response_structured = client.chat.completions.create(
                        model=config.STRUCTURED_MODEL,
                        messages=[
                            {"role": "system", "content": extraction_system_prompt},
                            {"role": "user", "content": extraction_user_prompt},
                        ],
                        response_format={
                            "type": "json_schema",
                            "schema": SearchPlanSchema.model_json_schema(),
                            "strict": True,
                        },
                        temperature=0.1,
                    )
                except Exception as e_schema:
                    logger.warning(
                        f"Structured outputs (schema) failed: {e_schema}. Falling back to JSON object mode."
                    )
                    response_structured = client.chat.completions.create(
                        model=config.STRUCTURED_MODEL,
                        messages=[
                            {
                                "role": "system",
                                "content": extraction_system_prompt
                                + " Always output valid JSON.",
                            },
                            {"role": "user", "content": extraction_user_prompt},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1,
                    )

                current_structured_output_str = (
                    response_structured.choices[0].message.content or ""
                )
                if not current_structured_output_str:
                    logger.warning("Structured LLM call returned empty content.")

                cleaned_output_str = current_structured_output_str.strip()
                if cleaned_output_str.startswith(
                    "```json"
                ) and cleaned_output_str.endswith("```"):
                    cleaned_output_str = cleaned_output_str[7:-3].strip()
                elif cleaned_output_str.startswith(
                    "```"
                ) and cleaned_output_str.endswith("```"):
                    cleaned_output_str = cleaned_output_str[3:-3].strip()

                current_parsed_plan_data = SearchPlanSchema.model_validate_json(
                    cleaned_output_str
                )

                structured_output_str = current_structured_output_str
                parsed_plan_data = current_parsed_plan_data
                logger.debug(
                    f"Successfully extracted and parsed structured output during this attempt."
                )

            attempt_structured_extraction()
            logger.info(
                f"Successfully parsed structured output from {config.STRUCTURED_MODEL} after retries (if any)."
            )
            logger.debug(
                f"Final Structured LLM Output: {structured_output_str[:500]}..."
            )

        except tenacity.RetryError as e:
            logger.error(
                f"Failed to get valid structured output from {config.STRUCTURED_MODEL} after multiple retries: {e}. Using fallback."
            )
            logger.error(
                f"Last attempted structured output (if available): {structured_output_str}"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during structured extraction attempts: {e}",
                exc_info=True,
            )
            logger.error(
                f"Last attempted structured output (if available): {structured_output_str}"
            )

        if parsed_plan_data:
            current_state_dict["target_country_locode"] = (
                parsed_plan_data.target_country_locode or state.target_country_locode
            )
            primary_langs = parsed_plan_data.primary_languages or []

            new_plan_items = []
            for sq in parsed_plan_data.search_queries:
                query_dict = sq.model_dump()
                query_dict["status"] = (
                    "pending"  # Ensure new queries are marked as pending
                )
                new_plan_items.append(query_dict)
            current_state_dict["search_plan"] = new_plan_items

            current_state_dict.setdefault("metadata", {})[
                "primary_languages"
            ] = primary_langs
            current_state_dict["metadata"]["key_institutions"] = (
                parsed_plan_data.key_institutions or []
            )
            current_state_dict["metadata"]["international_sources"] = (
                parsed_plan_data.international_sources or []
            )
            current_state_dict["metadata"]["document_types"] = (
                parsed_plan_data.document_types or []
            )
            current_state_dict["metadata"][
                "planner_confidence"
            ] = parsed_plan_data.confidence
            current_state_dict["metadata"][
                "planner_challenges"
            ] = parsed_plan_data.challenges

            # Save the structured output (JSON string from LLM)
            try:
                # Standardize log_dir to be consistent with raw output saving
                log_dir = os.path.join(os.getcwd(), "logs", "planner_outputs")
                os.makedirs(log_dir, exist_ok=True)  # Ensure directory exists

                country_name_sanitized = re.sub(
                    r"[^\w\-_]", "_", state.target_country or "UnknownCountry"
                )
                sector_name_sanitized = re.sub(
                    r"[^\w\-_]", "_", state.target_sector or "General"
                )
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                filename_structured = f"structured_output_{country_name_sanitized}_{sector_name_sanitized}_{timestamp}.json"
                filepath_structured = os.path.join(log_dir, filename_structured)
                with open(filepath_structured, "w", encoding="utf-8") as f:
                    f.write(structured_output_str)
                logger.info(
                    f"Saved structured planner LLM output to: {filepath_structured}"
                )
            except Exception as e:
                logger.error(f"Failed to save structured planner LLM output: {e}")

            log_summary = f"Plan for {state.target_country} with {len(new_plan_items)} structured queries."
            parsed_keywords_count = len(new_plan_items)
        else:
            logger.warning(
                f"Failed to get structured plan from {config.STRUCTURED_MODEL}. Using fallback query."
            )
            current_search_plan_fallback_structured = list(
                current_state_dict.get("search_plan", [])
            )
            current_search_plan_fallback_structured.append(
                {
                    "query": f"{state.target_country} GHGI data (structured fallback)",
                    "language": "en",
                    "priority": "high",
                    "status": "pending",
                    "target_type": "generic_fallback",
                }
            )
            current_state_dict["search_plan"] = current_search_plan_fallback_structured
            log_summary = f"Fallback plan for {state.target_country} due to structured parsing error."
            parsed_keywords_count = 1
            primary_langs = current_state_dict.get("metadata", {}).get(
                "primary_languages", []
            )

        current_state_dict["decision_log"].append(
            {
                "agent": "Planner",
                "action": "plan_generated",
                "summary": log_summary,
                "target_country_locode": current_state_dict["target_country_locode"],
                "primary_languages": primary_langs,
                "parsed_keywords_count": parsed_keywords_count,
                "structured_parsing_successful": parsed_plan_data is not None,
            }
        )

        logger.info(
            f"Planner node returning state with {len(current_state_dict['search_plan'])} search plan items."
        )

        final_planned_state = AgentState(**current_state_dict)
        logger.info(
            f"DEBUG_PLANNER: Returning state from planner. ID: {id(final_planned_state)}, Iteration: {final_planned_state.current_iteration}"
        )
        logger.info(
            f"PLANNER_NODE: About to return. Iteration in current_state_dict: {current_state_dict.get('current_iteration')}"
        )
        return final_planned_state

    except Exception as e:
        logger.error(
            f"Exception caught in planner_node: {type(e).__name__} - {e}", exc_info=True
        )
        logger.error(f"Planner state at time of error: country={state.target_country}")
        if llm_raw_output:
            logger.error(
                f"LLM Output (snippet) before error: {llm_raw_output[:500]}..."
            )
        else:
            logger.error(
                "LLM Output (snippet) before error: Not available or call did not complete."
            )

        error_search_plan = list(current_state_dict.get("search_plan", []))
        error_search_plan.append(
            {
                "query": f"{state.target_country} greenhouse gas inventory data (exception fallback)",
                "language": "en",
                "priority": "high",
                "status": "pending",
                "target_type": "exception_fallback",
            }
        )
        current_state_dict["search_plan"] = error_search_plan

        current_state_dict["decision_log"].append(
            {
                "agent": "Planner",
                "action": f"planner_failed_due_to_exception: {type(e).__name__}",
                "message": str(e),
                "details": f"LLM Raw Output: {llm_raw_output[:100]}...",
            }
        )

        logger.info(
            f"PLANNER_NODE: About to return. Iteration in current_state_dict: {current_state_dict.get('current_iteration')}"
        )
        return AgentState(**current_state_dict)


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG)  # COMMENTED OUT: Using centralized logging setup
    logger.info("Testing planner_node execution with structured output approach")
    if not config.OPENROUTER_API_KEY:
        logger.warning(
            "OPENROUTER_API_KEY not set; mock/fallback may be used depending on OPENAI_AVAILABLE."
        )

    test_country = "Germany"
    test_sector = "stationary_energy"
    test_state = create_initial_state(
        country_name=test_country, sector_name=test_sector
    )
    logger.info(
        f"Initial State: Country={test_state.target_country}, Sector={test_state.target_sector}, OPENAI_AVAILABLE={OPENAI_AVAILABLE}, STRUCTURED_MODEL={config.STRUCTURED_MODEL}"
    )

    updated_state = planner_node(test_state)
    logger.info("Planner node test executed.")

    if updated_state:
        try:
            logger.info(
                f"Decision log: {json.dumps(updated_state.decision_log, indent=2)}"
            )
        except TypeError:
            logger.info(f"Decision log (raw): {updated_state.decision_log}")

        logger.info(
            f"State: Country={updated_state.target_country} ({updated_state.target_country_locode}) P-Langs: {updated_state.metadata.get('primary_languages')}"
        )
        logger.info(f"Search Plan Items: {len(updated_state.search_plan)}")

        try:
            logger.info(
                f"Search Plan:\n{json.dumps(updated_state.search_plan, indent=2)}"
            )
        except TypeError:
            logger.info(f"Search Plan (raw): {updated_state.search_plan}")

        if updated_state.metadata and "structured_output" in updated_state.metadata:
            structured_output_for_log = updated_state.metadata["structured_output"]
            if isinstance(structured_output_for_log, str):
                snippet = {
                    k: v
                    for k, v in json.loads(structured_output_for_log).items()
                    if k in ["target_country_locode", "confidence", "search_queries"]
                }
                logger.info(
                    f"Parsed LLM (structured) snippet: {json.dumps(snippet, indent=2)}"
                )
            else:
                logger.info(
                    f"LLM Structured Plan Output (raw from metadata): {structured_output_for_log}"
                )
        elif (
            updated_state.metadata
            and "llm_planner_output_parsed" in updated_state.metadata
        ):
            logger.info(
                f"Old parsed data (regex): {updated_state.metadata['llm_planner_output_parsed']}"
            )
    else:
        logger.error("Planner node returned None/invalid state during test.")
