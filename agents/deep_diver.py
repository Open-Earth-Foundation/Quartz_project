"""
Agent responsible for processing deep dive requests from the reviewer.
Decides on the next concrete action (scrape or terminate) to dive deeper into existing websites.
"""
import logging
from typing import Dict, Any, Set, Optional, List
from datetime import datetime
from dataclasses import asdict
import json # Added for cleaning potential markdown in structured output
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type, before_sleep_log, RetryError
from pydantic import ValidationError # For specific exception handling

import config
from agent_state import AgentState
from agents.schemas import DeepDiveAction

logger = logging.getLogger(__name__)

# Path to the deep diver prompt template and output schema
DEEP_DIVER_PROMPT_PATH = Path(__file__).parent / "prompts" / "agent_deepdiver.md"
DEEP_DIVER_OUTPUT_SCHEMA_PATH = Path(__file__).parent / "prompts" / "deepdiver_output.json"

def load_deep_diver_prompt_template() -> str:
    """Loads the deep diver prompt template from file."""
    try:
        if DEEP_DIVER_PROMPT_PATH.exists():
            return DEEP_DIVER_PROMPT_PATH.read_text(encoding="utf-8")
        else:
            logger.error(f"Deep diver prompt file not found: {DEEP_DIVER_PROMPT_PATH}")
            return "" # Return empty string as fallback
    except Exception as e:
        logger.error(f"Error loading deep diver prompt file {DEEP_DIVER_PROMPT_PATH}: {e}")
        return ""

def load_deep_diver_output_schema() -> Optional[Dict[str, Any]]:
    """Loads the deep diver output JSON schema from file."""
    try:
        if DEEP_DIVER_OUTPUT_SCHEMA_PATH.exists():
            return json.loads(DEEP_DIVER_OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
        else:
            logger.error(f"Deep diver output schema file not found: {DEEP_DIVER_OUTPUT_SCHEMA_PATH}")
            return None
    except Exception as e:
        logger.error(f"Error loading/parsing deep diver output schema file {DEEP_DIVER_OUTPUT_SCHEMA_PATH}: {e}")
        return None

def extract_current_websites(state: AgentState) -> Set[str]:
    """Extract unique website domains from scraped data and structured data."""
    websites = set()
    
    # Extract from scraped data
    for item in state.scraped_data:
        url = item.get("url")
        if url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                if domain:
                    websites.add(domain)
            except Exception:
                continue
    
    # Extract from structured data
    for item in state.structured_data:
        url = item.get("url")
        if url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                if domain:
                    websites.add(domain)
            except Exception:
                continue
    
    return websites

async def deep_dive_processor_node(state: AgentState) -> AgentState:
    """
    Processes a deep dive request.
    Uses an LLM to determine the next action (scrape or terminate)
    based on refinement_details provided by the reviewer.
    Focuses on finding additional URLs within existing websites.
    """
    logger.info("Deep Dive Processor node activated.")

    # Update state counters at the beginning of deep dive processing
    state.consecutive_deep_dive_count += 1
    # Do NOT reset current_deep_dive_actions_count - it should persist for the deep dive cycle
    logger.info(f"Deep dive cycle started. Consecutive deep dives: {state.consecutive_deep_dive_count}, Actions in this cycle: {state.current_deep_dive_actions_count}")

    refinement_details = state.metadata.get("refinement_details")
    logger.info(f"Deep Dive Processor received refinement_details: '{refinement_details}'")

    if not refinement_details:
        logger.warning("No refinement_details found in metadata. Terminating deep dive.")
        action = DeepDiveAction(action_type="terminate_deep_dive", target=None, justification="No refinement details provided.")
        current_state_dict = asdict(state)
        current_state_dict["metadata"]["deep_dive_action"] = action.model_dump()
        current_state_dict.setdefault("decision_log", []).append({
            "agent": "DeepDiveProcessor", 
            "action": action.action_type,
            "timestamp": datetime.now().isoformat(),
            "justification": action.justification
        })
        return AgentState(**current_state_dict)

    # Check if deep dive action budget is exhausted for this cycle
    if state.current_deep_dive_actions_count >= config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE:
        logger.info(f"Max actions ({config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE}) for this deep dive cycle reached. Terminating deep dive.")
        action = DeepDiveAction(action_type="terminate_deep_dive", target=None, justification="Max actions per deep dive cycle reached.")
        state.metadata['deep_dive_action'] = action.model_dump()
        return state

    # Load prompt template and output schema
    prompt_template = load_deep_diver_prompt_template()
    output_json_schema = load_deep_diver_output_schema()
    
    if not prompt_template:
        logger.error("Failed to load deep diver prompt template. Terminating deep dive.")
        action = DeepDiveAction(action_type="terminate_deep_dive", target=None, justification="Failed to load prompt template.")
        state.metadata['deep_dive_action'] = action.model_dump()
        return state

    if not output_json_schema:
        logger.warning("Failed to load deep diver output schema. Will use fallback schema.")

    # Extract current websites for context
    current_websites = extract_current_websites(state)
    websites_list = list(current_websites)[:10]  # Limit to first 10 for prompt
    websites_str = ", ".join(websites_list) if websites_list else "None identified yet"

    # Format the prompt
    formatted_prompt = prompt_template.format(
        refinement_details=refinement_details,
        target_country=state.target_country or "Unknown",
        current_websites=websites_str,
        max_actions=config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE,
        actions_performed=state.current_deep_dive_actions_count
    )

    parsed_actions: List[Dict[str, Any]]
    raw_thinking_output = ""
    structured_llm_output_str = ""

    try:
        client = OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY)
        
        # --- First LLM Call (Thinking Model) ---
        thinking_model_to_use = config.THINKING_MODEL
        if not thinking_model_to_use:
            raise ValueError("No THINKING_MODEL configured for Deep Dive Processor.")

        logger.debug(f"Sending deep dive thinking prompt to {thinking_model_to_use}")
        
        thinking_response = client.chat.completions.create(
            model=thinking_model_to_use,
            messages=[
                {"role": "system", "content": "You are an AI assistant that analyzes websites to find additional specific URLs within the same domain for deeper data extraction. Focus on website navigation and structure."},
                {"role": "user", "content": formatted_prompt}
            ],
            # No specific response_format, allow free text for reasoning + JSON
            temperature=config.DEFAULT_TEMPERATURE,
        )
        raw_thinking_output = thinking_response.choices[0].message.content if thinking_response.choices[0].message.content else ""
        logger.debug(f"Deep Dive Processor (Thinking) LLM raw response: {raw_thinking_output}")

        if not raw_thinking_output:
            logger.warning("Deep Dive Processor (Thinking) LLM returned empty content.")
            raise ValueError("Thinking model returned empty content.")

        # --- Second LLM Call (Structured Model for JSON Extraction) ---
        structured_model_to_use = config.STRUCTURED_MODEL
        if not structured_model_to_use:
            raise ValueError("No STRUCTURED_MODEL configured for Deep Dive Processor JSON extraction.")

        extraction_system_prompt = "You are an AI assistant that extracts structured JSON data from text. Given a text that contains reasoning and a JSON object or array, extract *only* the JSON object or array. The JSON must conform to the provided schema. Do not include any explanations or conversational text in your output, only the JSON itself."
        extraction_user_prompt = f"""Extract the JSON object or JSON array from the following text. The JSON should represent a deep dive action (or list of actions) with 'action_type' (either 'scrape', 'crawl', or 'terminate_deep_dive'), 'target' (URL for scrape/crawl, null for terminate), 'justification', and optional 'max_pages' and 'exclude_patterns' for crawl actions.

            Text:
            ```
            {raw_thinking_output}
            ```

            Output only the JSON object or array.
            """
        
        logger.info(f"Sending text from {thinking_model_to_use} to {structured_model_to_use} for JSON extraction.")

        # Determine response format (standard and legacy)
        if output_json_schema:
            api_call_response_format_standard = {
                "type": "json_schema", 
                "json_schema": {
                    "name": "DeepDiverOutput",
                    "schema": output_json_schema,
                    "strict": True
                }
            }
            api_call_response_format_legacy = {"type": "json_schema", "json_schema": output_json_schema}
            logger.info(f"Using json_schema mode with schema loaded from {DEEP_DIVER_OUTPUT_SCHEMA_PATH} for {structured_model_to_use}.")
        else:
            api_call_response_format_standard = {"type": "json_object"}
            api_call_response_format_legacy = {"type": "json_object"}
            logger.warning(f"Schema from file {DEEP_DIVER_OUTPUT_SCHEMA_PATH} not loaded. Defaulting to json_object mode for {structured_model_to_use}.")

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_fixed(2),
            retry=retry_if_exception_type((ValidationError, json.JSONDecodeError, ValueError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def attempt_structured_extraction(response_format):
            nonlocal structured_llm_output_str
            extraction_response = client.chat.completions.create(
                model=structured_model_to_use,
                messages=[
                    {"role": "system", "content": extraction_system_prompt},
                    {"role": "user", "content": extraction_user_prompt}
                ],
                response_format=response_format,
                temperature=config.DEFAULT_TEMPERATURE 
            )
            current_structured_output = extraction_response.choices[0].message.content or ""
            
            # Clean potential markdown ```json ... ```
            cleaned_output = current_structured_output.strip()
            if cleaned_output.startswith("```json") and cleaned_output.endswith("```"):
                cleaned_output = cleaned_output[7:-3].strip()
            elif cleaned_output.startswith("```") and cleaned_output.endswith("```"): # Handle ``` only
                cleaned_output = cleaned_output[3:-3].strip()
            
            structured_llm_output_str = cleaned_output
            if not structured_llm_output_str:
                raise ValueError("Structured model returned empty content for JSON extraction.")
            
            # Parse JSON and allow either a single object or a list of actions.
            parsed_json = json.loads(structured_llm_output_str)
            if isinstance(parsed_json, list):
                if not parsed_json:
                    raise ValueError("LLM returned an empty array.")
                logger.warning("LLM returned an array of actions. Validating all entries.")
                raw_actions = parsed_json
            else:
                raw_actions = [parsed_json]

            validated_actions: List[Dict[str, Any]] = []
            for raw_action in raw_actions:
                action_model = DeepDiveAction.model_validate(raw_action)
                validated_actions.append(action_model.model_dump())
            return validated_actions

        # Try standard format first, then fallback to legacy
        try:
            if output_json_schema:
                logger.info("Attempting deep diver extraction with OpenAI-compliant json_schema format.")
            parsed_actions = attempt_structured_extraction(api_call_response_format_standard)
            if output_json_schema:
                logger.info("Successfully used OpenAI-compliant json_schema format for deep diver.")
        except Exception as e:
            if output_json_schema and ("BadRequestError" in str(type(e).__name__) or "400" in str(e) or "json_schema" in str(e).lower()):
                logger.warning(f"OpenAI-compliant format failed for deep diver: {e}. Falling back to legacy format.")
                logger.info("Attempting deep diver extraction with legacy json_schema format.")
                parsed_actions = attempt_structured_extraction(api_call_response_format_legacy)
                logger.info("Successfully used legacy json_schema format for deep diver.")
            else:
                raise
        
    except RetryError as e_retry: # Tenacity retry error
        logger.error(f"Failed to extract valid JSON for Deep Dive Action after multiple retries: {e_retry}. Last raw output from structured model: '{structured_llm_output_str}'. Terminating deep dive.")
        parsed_actions = [{"action_type": "terminate_deep_dive", "justification": f"JSON extraction failed after retries: {e_retry}"}]
    except (ValueError, ValidationError, json.JSONDecodeError) as e_val: # Catch errors from thinking model emptiness, or final validation if retry somehow bypassed
        logger.error(f"Failed to parse or validate Deep Dive Processor LLM JSON response: {e_val}. Raw structured output: '{structured_llm_output_str}'. Raw thinking output: '{raw_thinking_output[:500]}...'. Terminating deep dive.")
        parsed_actions = [{"action_type": "terminate_deep_dive", "justification": f"LLM response processing error: {e_val}"}]
    except Exception as e: # Catch-all for other unexpected errors
        logger.error(f"Unexpected error in Deep Dive Processor node: {e}", exc_info=True)
        parsed_actions = [{"action_type": "terminate_deep_dive", "justification": f"Unhandled error in deep_dive_processor_node: {e}"}]

    if isinstance(parsed_actions, dict):
        parsed_actions_list = [parsed_actions]
    else:
        parsed_actions_list = parsed_actions or []

    if not parsed_actions_list:
        parsed_actions_list = [{
            "action_type": "terminate_deep_dive",
            "justification": "No deep dive actions were returned by the model."
        }]

    normalized_actions: List[Dict[str, Any]] = []
    for action in parsed_actions_list:
        if not isinstance(action, dict):
            normalized_actions.append({
                "action_type": "terminate_deep_dive",
                "target": None,
                "justification": "Invalid deep dive action format; expected object."
            })
            continue

        action_type = action.get("action_type")
        if action_type not in ["scrape", "crawl", "terminate_deep_dive"]:
            logger.warning(f"Invalid action type '{action_type}'. Forcing termination.")
            normalized_actions.append({
                "action_type": "terminate_deep_dive",
                "target": None,
                "justification": f"Invalid action type '{action_type}' provided."
            })
            continue

        normalized_action = dict(action)
        if action_type == "terminate_deep_dive":
            normalized_action["target"] = None
        elif action_type in ["scrape", "crawl"] and not normalized_action.get("target"):
            logger.warning(f"{action_type} action chosen but no target URL provided. Forcing termination.")
            normalized_action = {
                "action_type": "terminate_deep_dive",
                "target": None,
                "justification": f"{action_type} action requires a target URL."
            }

        if normalized_action.get("action_type") == "crawl":
            max_pages = normalized_action.get("max_pages", 10)
            if max_pages > 50:
                logger.warning(f"Crawl max_pages ({max_pages}) exceeds safety limit. Capping at 50.")
                normalized_action["max_pages"] = 50

        normalized_actions.append(normalized_action)

    actionable_actions = [
        action for action in normalized_actions if action.get("action_type") in ["scrape", "crawl"]
    ]

    if actionable_actions:
        remaining_budget = max(
            0,
            config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE - state.current_deep_dive_actions_count
        )
        if remaining_budget <= 0:
            actionable_actions = []
        elif len(actionable_actions) > remaining_budget:
            logger.warning(
                "Deep dive returned %s actions but only %s actions remain in the budget. Truncating.",
                len(actionable_actions),
                remaining_budget
            )
            actionable_actions = actionable_actions[:remaining_budget]

    if actionable_actions:
        state.metadata["deep_dive_actions"] = actionable_actions
        state.metadata["deep_dive_action"] = actionable_actions[0]
        state.current_deep_dive_actions_count += len(actionable_actions)
        logger.info(
            "Deep Dive actions enqueued: %s. Actions taken this cycle: %s",
            len(actionable_actions),
            state.current_deep_dive_actions_count
        )
        action_log_entry = actionable_actions[0]
        log_action_type = "batch" if len(actionable_actions) > 1 else action_log_entry.get("action_type")
        log_target = action_log_entry.get("target")
        log_justification = action_log_entry.get("justification")
    else:
        terminate_action = {
            "action_type": "terminate_deep_dive",
            "target": None,
            "justification": "No actionable deep dive actions after validation."
        }
        state.metadata.pop("deep_dive_actions", None)
        state.metadata["deep_dive_action"] = terminate_action
        logger.info("Deep Dive action: terminate_deep_dive. Justification: %s", terminate_action.get("justification"))
        log_action_type = terminate_action.get("action_type")
        log_target = terminate_action.get("target")
        log_justification = terminate_action.get("justification")

    decision_log_entry = {
        "agent": "DeepDiveProcessor",
        "action": log_action_type,
        "target": log_target,
        "justification": log_justification,
        "refinement_details_processed": refinement_details,
        "actions_this_cycle": state.current_deep_dive_actions_count,
        "current_websites_considered": websites_str,
        "timestamp": datetime.now().isoformat()
    }
    if actionable_actions and len(actionable_actions) > 1:
        decision_log_entry["actions"] = actionable_actions

    state.decision_log.append(decision_log_entry)
    
    return state 
