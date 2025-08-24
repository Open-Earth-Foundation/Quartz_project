import logging
import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from datetime import datetime
import re
from openai import OpenAI
import tenacity
from pydantic import ValidationError
OPENAI_AVAILABLE = True



import config
from agent_state import AgentState, create_initial_state # For testing
from agents.schemas import RawReviewerLLMResponse, StructuredDataItem, ReviewerLLMResponse # StructuredDataItem for type hint and input prep

# Setup logging
logger = logging.getLogger(__name__)
RAW_PROMPT_FILE_PATH = os.path.join(os.path.dirname(__file__), "prompts", "ccra_reviewer.md")
STRUCTURED_PROMPT_FILE_PATH = os.path.join(os.path.dirname(__file__), "prompts", "ccra_reviewer_structured.md")
STRUCTURED_REVIEWER_OUTPUT_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "prompts", "reviewer_structured_output.json")
STRUCTURED_REVIEWER_FINAL_DECISION_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "prompts", "reviewer_structured_output_final_decision.json")

def load_raw_reviewer_prompt_template() -> str:
    """Loads the raw reviewer prompt template from file."""
    try:
        with open(RAW_PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error loading raw reviewer prompt file {RAW_PROMPT_FILE_PATH}: {e}")
        return ""

def load_structured_reviewer_user_prompt() -> str:
    """Loads the structured reviewer user prompt template from file."""
    try:
        with open(STRUCTURED_PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error loading structured reviewer user prompt file {STRUCTURED_PROMPT_FILE_PATH}: {e}")
        return ""

def load_structured_reviewer_output_schema() -> Optional[Dict[str, Any]]:
    """Loads the structured reviewer output JSON schema from file."""
    try:
        with open(STRUCTURED_REVIEWER_OUTPUT_SCHEMA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading/parsing structured reviewer output schema file {STRUCTURED_REVIEWER_OUTPUT_SCHEMA_PATH}: {e}")
        return None

def load_structured_reviewer_final_decision_schema() -> Optional[Dict[str, Any]]:
    """Loads the structured reviewer final decision output JSON schema from file."""
    try:
        with open(STRUCTURED_REVIEWER_FINAL_DECISION_SCHEMA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading/parsing structured reviewer final decision schema file {STRUCTURED_REVIEWER_FINAL_DECISION_SCHEMA_PATH}: {e}")
        return None

def reviewer_node(state: AgentState) -> AgentState:
    """
    This node performs the RAW CONTENT REVIEW.
    It takes a list of scraped web documents (raw text/markdown snippets).
    An LLM call is made to assess these raw documents, select promising ones for extraction,
    and suggest the next step (e.g., proceed_to_extraction).
    The schema for this LLM call is dynamically generated from RawReviewerLLMResponse.
    """
    logger.info("Reviewer node activated for raw content review.")
    current_state_dict = asdict(state)
    current_state_dict["selected_for_extraction"] = [] 

    if not OPENAI_AVAILABLE or not config.OPENROUTER_API_KEY:
        msg = "OpenAI library not installed." if not OPENAI_AVAILABLE else "OpenRouter API key not configured."
        logger.error(f"{msg} Reviewer node cannot function fully. Returning fallback decision.")
        current_state_dict.setdefault("decision_log", []).append({
            "agent": "Reviewer", "action": "error_fallback_raw_review", "timestamp": datetime.now().isoformat(),
            "message": msg, "suggested_action": "end"
        })
        current_state_dict.setdefault("metadata", {})["next_step_after_review"] = "end"
        return AgentState(**current_state_dict)

    prompt_template = load_raw_reviewer_prompt_template()

    if not prompt_template:
        logger.error("Failed to load raw reviewer prompt template. Aborting reviewer.")
        current_state_dict.setdefault("decision_log", []).append({
            "agent": "Reviewer", "action": "error_raw_review", "timestamp": datetime.now().isoformat(),
            "message": "Failed to load raw reviewer prompt template.", "suggested_action": "end"
        })
        current_state_dict.setdefault("metadata", {})["next_step_after_review"] = "end"
        return AgentState(**current_state_dict)

    target_location = state.target_country or state.target_city or "Global"
    ccra_context = f"{state.target_mode} {state.target_which}" if state.target_mode and state.target_which else "climate risk assessment"

    if not state.scraped_data:
        logger.info("No scraped data found to review. Skipping reviewer action, suggesting END.")
        current_state_dict.setdefault("decision_log", []).append({
            "agent": "Reviewer", "action": "skip_no_scraped_data", "timestamp": datetime.now().isoformat(),
            "message": "No scraped data provided for raw review.", "suggested_action": "end"
        })
        current_state_dict.setdefault("metadata", {})["next_step_after_review"] = "end"
        return AgentState(**current_state_dict)
        
    MAX_SNIPPET_LENGTH = config.MAX_REVIEWER_SNIPPET_LENGTH if hasattr(config, 'MAX_REVIEWER_SNIPPET_LENGTH') else 2000
    MAX_DOCS_FOR_REVIEW = config.MAX_DOCS_FOR_REVIEW if hasattr(config, 'MAX_DOCS_FOR_REVIEW') else 15
    
    scraped_documents_for_prompt = []
    for doc in state.scraped_data[:MAX_DOCS_FOR_REVIEW]:
        content = doc.get('content', doc.get('markdown', ''))
        snippet = content[:MAX_SNIPPET_LENGTH] if content else "No content available"
        scraped_documents_for_prompt.append({
            "url": doc.get("url"),
            "content_snippet": snippet
        })
    
    if not scraped_documents_for_prompt:
        logger.info("No processable scraped data snippets for review. Suggesting END.")
        current_state_dict.setdefault("decision_log", []).append({
            "agent": "Reviewer", "action": "skip_no_snippets", "timestamp": datetime.now().isoformat(),
            "message": "No valid snippets could be generated from scraped data for raw review.", "suggested_action": "end"
        })
        current_state_dict.setdefault("metadata", {})["next_step_after_review"] = "end"
        return AgentState(**current_state_dict)
        
    scraped_documents_json_str = json.dumps(scraped_documents_for_prompt, indent=2)

    formatted_user_prompt = prompt_template.replace("{target_country_name}", target_location or "Unknown Location")
    formatted_user_prompt = formatted_user_prompt.replace("{target_sector}", ccra_context or "climate risk assessment")
    formatted_user_prompt = formatted_user_prompt.replace("{ccra_mode}", state.target_mode or "Unknown Mode")
    formatted_user_prompt = formatted_user_prompt.replace("{ccra_type}", state.target_which or "Unknown Type")
    formatted_user_prompt = formatted_user_prompt.replace("{scraped_documents_json}", scraped_documents_json_str)
    
    system_prompt = f"You are a helpful AI assistant designed to review climate risk assessment documents and identify relevant {ccra_context} datasets according to user instructions. Output JSON conforming to the provided schema."
    
    llm_response_parsed: Optional[RawReviewerLLMResponse] = None
    llm_raw_output = ""

    pydantic_response_format = {"type": "json_schema", "json_schema": RawReviewerLLMResponse.model_json_schema()}
    logger.info(f"Using json_schema mode with dynamically generated schema from RawReviewerLLMResponse for raw reviewer.")

    try:
        client = OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY)

        messages_for_llm = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": formatted_user_prompt}
        ]

        def should_retry_reviewer(exception):
            return isinstance(exception, (TypeError, AttributeError, IndexError, json.JSONDecodeError, ValidationError))

        @tenacity.retry(
            stop=tenacity.stop_after_attempt(config.MAX_RETRY_ATTEMPTS if hasattr(config, 'MAX_RETRY_ATTEMPTS') else 3),
            wait=tenacity.wait_fixed(config.BASE_RETRY_DELAY if hasattr(config, 'BASE_RETRY_DELAY') else 2),
            retry=tenacity.retry_if_exception(should_retry_reviewer),
            before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def attempt_raw_review_extraction():
            nonlocal llm_raw_output, llm_response_parsed

            response = client.chat.completions.create(
                model=config.STRUCTURED_MODEL,
                messages=messages_for_llm,
                response_format=pydantic_response_format,
                temperature=0.1
            )
            
            current_llm_raw_output = response.choices[0].message.content or ""
            if not current_llm_raw_output:
                 logger.warning("Raw Reviewer LLM returned empty content.")

            cleaned_llm_output = current_llm_raw_output.strip()
            if cleaned_llm_output.startswith("```json") and cleaned_llm_output.endswith("```"):
                cleaned_llm_output = cleaned_llm_output[7:-3].strip()
            elif cleaned_llm_output.startswith("```") and cleaned_llm_output.endswith("```"):
                 cleaned_llm_output = cleaned_llm_output[3:-3].strip()

            current_llm_response_parsed = RawReviewerLLMResponse.model_validate_json(cleaned_llm_output)

            llm_raw_output = current_llm_raw_output
            llm_response_parsed = current_llm_response_parsed
           
        attempt_raw_review_extraction()
        
        if llm_response_parsed:
            logger.info(f"Successfully parsed raw reviewer LLM response. Suggested next action: {llm_response_parsed.suggested_next_action}. Docs to extract: {len(llm_response_parsed.documents_to_extract)}")
        else:
            logger.warning("Parsing raw reviewer LLM response potentially failed after retries, llm_response_parsed is None.")

    except tenacity.RetryError as e:
        logger.error(f"Failed to get valid raw review output from {config.STRUCTURED_MODEL} after multiple retries: {e}. Using fallback.")
        logger.error(f"Last raw output attempted (if available): {llm_raw_output[:500]}...")
    except Exception as e:
        logger.error(f"Error calling Raw Reviewer LLM or parsing response: {type(e).__name__} - {e}", exc_info=True)
        logger.error(f"LLM raw output before error (if any): {llm_raw_output[:500]}...")

    final_action = "end"
    decision_log_entry: Dict[str, Any] = {"agent": "Reviewer", "timestamp": datetime.now().isoformat()}
    
    if llm_response_parsed:
        current_state_dict["selected_for_extraction"] = llm_response_parsed.documents_to_extract
        final_action = llm_response_parsed.suggested_next_action
        current_state_dict.setdefault("metadata", {})["last_raw_review_details"] = llm_response_parsed.model_dump()
        decision_log_entry["action"] = "raw_review_completed"
        decision_log_entry["suggested_action"] = final_action
        decision_log_entry["documents_selected_for_extraction_count"] = len(llm_response_parsed.documents_to_extract)
        decision_log_entry["summary"] = llm_response_parsed.overall_assessment
        decision_log_entry["reasoning"] = llm_response_parsed.action_reasoning

        if final_action == "proceed_to_extraction" and not llm_response_parsed.documents_to_extract:
            logger.warning("Reviewer suggested 'proceed_to_extraction' but selected no documents. Changing action to 'refine_plan'.")
            final_action = "refine_plan"
            decision_log_entry["suggested_action"] = final_action
            decision_log_entry["reasoning"] = (decision_log_entry.get("reasoning", "") + 
                                                 " Switched to refine_plan as no documents were selected for extraction.").strip()
            if "last_raw_review_details" in current_state_dict["metadata"]:
                 current_state_dict["metadata"]["last_raw_review_details"]["suggested_next_action"] = final_action

    else: 
        logger.warning(f"Using fallback action: {final_action} due to LLM/parsing issues in raw review.")
        current_state_dict.setdefault("metadata", {})["last_raw_review_details"] = {
            "overall_assessment": "Fallback: LLM call or parsing failed for raw content review.",
            "suggested_next_action": final_action,
            "action_reasoning": "Error during LLM interaction or response processing for raw review."
        }
        decision_log_entry["action"] = "raw_review_failed_fallback"
        decision_log_entry["suggested_action"] = final_action
        decision_log_entry["message"] = "LLM call for raw review failed or parsing error."

    current_state_dict.setdefault("metadata", {})["next_step_after_review"] = final_action
    current_state_dict.setdefault("decision_log", []).append(decision_log_entry)
    current_state_dict["current_iteration"] = state.current_iteration

    logger.info(f"Reviewer node (raw content) finished. Suggested next step: {current_state_dict['metadata'].get('next_step_after_review')}. Documents selected for extraction: {len(current_state_dict.get('selected_for_extraction', []))}")
    return AgentState(**current_state_dict)


def structured_data_reviewer_node(state: AgentState) -> AgentState:
    """
    This node performs the STRUCTURED DATA REVIEW.
    It is called after the ExtractorAgent has processed documents and produced structured data.
    An LLM call is made to review this extracted structured data for relevance, credibility, and completeness.
    It suggests a final action: accept, reject, or deep_dive (only if no deep dive has been performed yet).
    The schema for this LLM call will be loaded from 'agents/prompts/reviewer_structured_output.json' or
    'agents/prompts/reviewer_structured_output_final_decision.json' depending on deep dive status.
    """
    logger.info(f"STRUCTURED_REVIEWER_NODE: Entered. Current iteration: {state.current_iteration}, consecutive deep dives: {state.consecutive_deep_dive_count}")
    current_state_dict = asdict(state)
    current_state_dict.setdefault("metadata", {})["refinement_details"] = None

    # Determine if this is a final decision (no more deep dives allowed)
    is_final_decision = state.consecutive_deep_dive_count >= 1
    
    if is_final_decision:
        logger.info(f"FINAL DECISION MODE: One deep dive already performed (count: {state.consecutive_deep_dive_count}). Reviewer must choose accept or reject only.")
    else:
        logger.info(f"INITIAL REVIEW MODE: No deep dives performed yet. All options (accept/reject/deep_dive) available.")

    if not OPENAI_AVAILABLE or not config.OPENROUTER_API_KEY:
        msg = "OpenAI library not installed." if not OPENAI_AVAILABLE else "OpenRouter API key not configured."
        logger.error(f"{msg} Structured Data Reviewer node cannot function fully. Returning fallback decision.")
        current_state_dict.setdefault("decision_log", []).append({
            "agent": "StructuredReviewer", "action": "error_fallback_structured_review", "timestamp": datetime.now().isoformat(),
            "message": msg, "suggested_action": "reject"
        })
        current_state_dict.setdefault("metadata", {})["next_step_after_structured_review"] = "reject"
        return AgentState(**current_state_dict)

    user_prompt_template_str = load_structured_reviewer_user_prompt()
    
    # Load appropriate schema based on deep dive status
    if is_final_decision:
        output_json_schema = load_structured_reviewer_final_decision_schema()
        schema_file_used = STRUCTURED_REVIEWER_FINAL_DECISION_SCHEMA_PATH
    else:
        output_json_schema = load_structured_reviewer_output_schema()
        schema_file_used = STRUCTURED_REVIEWER_OUTPUT_SCHEMA_PATH

    if not user_prompt_template_str or not output_json_schema:
        error_msg = ""
        if not user_prompt_template_str:
            error_msg += "Failed to load structured reviewer user prompt. "
        if not output_json_schema:
            error_msg += f"Failed to load structured reviewer output schema from file {schema_file_used}. "
        logger.error(error_msg.strip() + " Cannot proceed with structured review. Falling back to reject.")
        
        current_state_dict.setdefault("decision_log", []).append({
            "agent": "StructuredReviewer", "action": "error_structured_review_load_files", "timestamp": datetime.now().isoformat(),
            "message": error_msg.strip(), "suggested_action": "reject"
        })
        current_state_dict.setdefault("metadata", {})["next_step_after_structured_review"] = "reject"
        fallback_response = ReviewerLLMResponse(
            overall_assessment_notes="Fallback: Critical error loading prompt or schema.",
            relevance_score="Low", relevance_reasoning="File loading error.",
            credibility_score="Low", credibility_reasoning="File loading error.",
            completeness_score="Low", completeness_reasoning="File loading error.",
            overall_confidence="Low",
            suggested_action="reject",
            action_reasoning="System error: Failed to load required files for structured review.",
            refinement_details=None
        )
        current_state_dict.setdefault("metadata", {})["last_structured_review_details"] = fallback_response.model_dump()
        current_state_dict.setdefault("metadata", {})["next_step_after_structured_review"] = "reject"
        return AgentState(**current_state_dict)

    target_location = state.target_country or state.target_city or "Global"
    target_locode = state.target_country_locode or "N/A"
    ccra_context = f"{state.target_mode} {state.target_which}" if state.target_mode and state.target_which else "climate risk assessment"

    if not state.structured_data:
        logger.info("No structured data found to review. Suggesting reject as no data is available.")
        current_state_dict.setdefault("decision_log", []).append({
            "agent": "StructuredReviewer", "action": "skip_no_structured_data", "timestamp": datetime.now().isoformat(),
            "message": "No structured data provided for review.", "suggested_action": "reject"
        })
        current_state_dict.setdefault("metadata", {})["next_step_after_structured_review"] = "reject"
        return AgentState(**current_state_dict)
        
    search_plan_snippet_str = json.dumps(state.search_plan[:3], indent=2) if state.search_plan else "[]"
    structured_data_json_str = json.dumps(state.structured_data, indent=2)

    doc_summary_list = []
    processed_urls_for_summary = set()
    for item in state.structured_data:
        if item.get("url") and item.get("url") not in processed_urls_for_summary:
            doc_summary_list.append({"url": item.get("url"), "name": item.get("name", "N/A")})
            processed_urls_for_summary.add(item.get("url"))
    if not doc_summary_list and state.scraped_data:
         for item in state.scraped_data:
            if item.get("url") and item.get("url") not in processed_urls_for_summary:
                doc_summary_list.append({"url": item.get("url"), "title": item.get("metadata", {}).get("title", "N/A")})
                processed_urls_for_summary.add(item.get("url"))
    documents_summary_json_str = json.dumps(doc_summary_list[:10], indent=2)

    # Prepare conditional prompt content based on deep dive status
    if is_final_decision:
        deep_dive_status_message = f"**IMPORTANT: This is a FINAL DECISION after {state.consecutive_deep_dive_count} deep dive(s). You must choose either ACCEPT or REJECT. No more deep dives are allowed.**"
        deep_dive_section = "~~**DEEP_DIVE option is NOT AVAILABLE** - Final decision required.~~"
        available_actions_note = "**Available actions**: You must choose between 'accept' or 'reject' only."
        available_actions = "Must be one of 'accept' or 'reject'"
    else:
        deep_dive_status_message = "**Status**: Initial review - all decision options are available."
        deep_dive_section = """**DEEP_DIVE** if:

- Promising sources were found but need deeper investigation (max 1-2 attempts)
- Specific datasets mentioned but need direct access
- Government sites found but need to explore sub-pages for detailed data"""
        available_actions_note = "**Available actions**: You can choose 'accept', 'reject', or 'deep_dive'."
        available_actions = "Must be one of 'accept', 'deep_dive', or 'reject'"

    try:
        # DIAGNOSTIC LOGGING
        logger.info(f"STRUCTURED_REVIEWER_TEMPLATE_DEBUG: About to format. Template is: <<< {user_prompt_template_str[:500]} >>>")
        
        # Specific try-except for the format call itself
        try:
            user_prompt = user_prompt_template_str.format(
                target_country_name=target_location or "Unknown Location",
                target_country_locode=target_locode,
                ccra_mode=state.target_mode or "Unknown Mode",
                ccra_type=state.target_which or "Unknown Type",
                ccra_context=ccra_context,
                search_plan_snippet=search_plan_snippet_str,
                documents_summary_json=documents_summary_json_str,
                structured_data_json=structured_data_json_str,
                deep_dive_status_message=deep_dive_status_message,
                deep_dive_section=deep_dive_section,
                available_actions_note=available_actions_note,
                available_actions=available_actions
            )
        except KeyError as ke:
            logger.error(f"STRUCTURED_REVIEWER_FORMAT_KEY_ERROR: Key not found during prompt formatting: {ke}", exc_info=True)
            logger.error(f"STRUCTURED_REVIEWER_FORMAT_KEY_ERROR_TEMPLATE_USED: <<< {user_prompt_template_str[:1000]} >>>")
            raise # Re-raise the error
        except Exception as e_fmt:
            logger.error(f"STRUCTURED_REVIEWER_FORMAT_GENERAL_ERROR: Error during prompt formatting: {type(e_fmt).__name__} - {e_fmt}", exc_info=True)
            logger.error(f"STRUCTURED_REVIEWER_FORMAT_GENERAL_ERROR_TEMPLATE_USED: <<< {user_prompt_template_str[:1000]} >>>")
            raise # Re-raise
            
    except Exception as e_outer: # Catch if the above re-raise or other issues occur before this point
        logger.error(f"Error in structured_data_reviewer_node before LLM call (possibly during prompt setup): {type(e_outer).__name__} - {e_outer}", exc_info=True)
        # Ensure user_prompt is a string to prevent downstream errors if it wasn't set due to an early exception
        user_prompt = "Fallback prompt due to critical formatting error. Check logs."
        # Fallback to reject if prompt formatting fails catastrophically before LLM call can be made
        # This code path leads to the LLM call potentially being skipped if formatting fails and error is not re-raised by inner block
        # However, the inner block now re-raises, so this outer `except` might mostly catch things *before* the inner try.

    system_prompt = f"You are an AI assistant performing critical review of structured data for Climate Change Risk Assessment (CCRA) research, specifically focusing on {ccra_context} datasets. Output your response in the specified JSON format, adhering to the schema provided by the system."

    llm_response_parsed: Optional[ReviewerLLMResponse] = None
    llm_raw_output = ""

    logger.info(f"Sending structured data review request to {config.STRUCTURED_MODEL} for {ccra_context} in {target_location}. Final decision mode: {is_final_decision}")

    try:
        client = OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY)

        
        messages_for_llm = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        if output_json_schema:
            api_call_response_format = {"type": "json_schema", "json_schema": output_json_schema}
            logger.info(f"Using json_schema mode with schema loaded from {schema_file_used} for {config.STRUCTURED_MODEL}. Final decision: {is_final_decision}")
        else:
            api_call_response_format = {"type": "json_object"}
            logger.warning(f"Schema from file {schema_file_used} not loaded. Defaulting to json_object mode for {config.STRUCTURED_MODEL}.")

        @tenacity.retry(
            stop=tenacity.stop_after_attempt(config.MAX_RETRY_ATTEMPTS if hasattr(config, 'MAX_RETRY_ATTEMPTS') else 3),
            wait=tenacity.wait_fixed(config.BASE_RETRY_DELAY if hasattr(config, 'BASE_RETRY_DELAY') else 2),
            retry=tenacity.retry_if_exception(lambda e: isinstance(e, (json.JSONDecodeError, ValidationError, TypeError, AttributeError, IndexError))),
            before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def attempt_structured_review_extraction():
            nonlocal llm_raw_output, llm_response_parsed
            
            response = client.chat.completions.create(
                model=config.STRUCTURED_MODEL, 
                messages=messages_for_llm,
                response_format=api_call_response_format,
                temperature=0.1
            )
            current_llm_raw_output = response.choices[0].message.content or ""
            cleaned_output = current_llm_raw_output.strip()
            if cleaned_output.startswith("```json") and cleaned_output.endswith("```"):
                cleaned_output = cleaned_output[7:-3].strip()
            elif cleaned_output.startswith("```") and cleaned_output.endswith("```"):
                cleaned_output = cleaned_output[3:-3].strip()
            
            llm_response_parsed = ReviewerLLMResponse.model_validate_json(cleaned_output)
            llm_raw_output = current_llm_raw_output
        
        attempt_structured_review_extraction()
        
        if llm_response_parsed:
            logger.info(f"Successfully parsed structured reviewer LLM response. Suggested action: {llm_response_parsed.suggested_action}")
            
            # Validate that deep_dive is not suggested when in final decision mode
            if is_final_decision and llm_response_parsed.suggested_action == "deep_dive":
                logger.warning(f"VALIDATION ERROR: LLM suggested 'deep_dive' in final decision mode. Forcing 'reject' instead.")
                llm_response_parsed.suggested_action = "reject"
                llm_response_parsed.action_reasoning = f"Original LLM suggestion was deep_dive, but changed to reject because final decision required after {state.consecutive_deep_dive_count} deep dive(s). Original reasoning: {llm_response_parsed.action_reasoning}"
                
        else: 
             logger.error("LLM response parsing failed for structured review even after retries or retry logic bypassed.")
             raise ValueError("Failed to parse structured review LLM response (llm_response_parsed is None post-retry).")

    except Exception as e: 
        logger.error(f"Error in Structured Reviewer LLM call or parsing: {type(e).__name__} - {e}", exc_info=True)
        logger.error(f"LLM raw output for structured review (if any): {llm_raw_output[:500]}...")
        llm_response_parsed = ReviewerLLMResponse(
            overall_assessment_notes=f"Fallback: LLM call or parsing failed for structured review. Error: {type(e).__name__}",
            relevance_score="Low", relevance_reasoning="Fallback due to error.",
            credibility_score="Low", credibility_reasoning="Fallback due to error.",
            completeness_score="Low", completeness_reasoning="Fallback due to error.",
            overall_confidence="Low",
            suggested_action="reject",
            action_reasoning=f"Error during LLM interaction or response processing for structured review: {e}",
            refinement_details=None
        )

    final_action = llm_response_parsed.suggested_action
    current_state_dict.setdefault("metadata", {})["next_step_after_structured_review"] = final_action
    current_state_dict.setdefault("metadata", {})["last_structured_review_details"] = llm_response_parsed.model_dump()
    
    # Reset consecutive deep dive count for non-deep_dive actions
    if final_action != "deep_dive":
        current_state_dict["consecutive_deep_dive_count"] = 0
        logger.info(f"Resetting consecutive_deep_dive_count to 0 since action is '{final_action}', not 'deep_dive'")
    
    if final_action == "deep_dive":
        if is_final_decision:
            # This should not happen due to validation above, but double-check
            logger.error(f"CRITICAL ERROR: deep_dive action in final decision mode! This should have been prevented. Forcing reject.")
            final_action = "reject"
            current_state_dict.setdefault("metadata", {})["next_step_after_structured_review"] = "reject"
        else:
            if llm_response_parsed.refinement_details:
                current_state_dict["metadata"]["refinement_details"] = llm_response_parsed.refinement_details
                logger.info(f"Deep dive suggested. Refinement details: {llm_response_parsed.refinement_details}")
            else:
                fallback_details = llm_response_parsed.action_reasoning if llm_response_parsed.action_reasoning else "LLM suggested deep dive but provided no specific details."
                current_state_dict["metadata"]["refinement_details"] = fallback_details
                logger.warning(f"Deep dive suggested, but refinement_details was not directly provided by LLM. Using action_reasoning or default: {fallback_details}")
    
    decision_log_entry: Dict[str, Any] = {
        "agent": "StructuredReviewer", "timestamp": datetime.now().isoformat(),
        "action": "structured_review_completed",
        "suggested_action": final_action,
        "overall_confidence": llm_response_parsed.overall_confidence,
        "summary": llm_response_parsed.overall_assessment_notes,
        "reasoning": llm_response_parsed.action_reasoning,
        "final_decision_mode": is_final_decision,
        "consecutive_deep_dive_count": state.consecutive_deep_dive_count
    }
    current_state_dict.setdefault("decision_log", []).append(decision_log_entry)
    
    logger.info(f"Structured Data Reviewer node finished. Suggested next step: {current_state_dict['metadata'].get('next_step_after_structured_review')}. Current Iteration: {current_state_dict.get('current_iteration')}. Final decision mode: {is_final_decision}")
    
    final_state_obj = AgentState(**current_state_dict)
    logger.info(f"STRUCTURED_REVIEWER_NODE: Exiting. Iteration in final_state_obj: {final_state_obj.current_iteration}")
    return final_state_obj

if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')  # COMMENTED OUT: Using centralized logging setup
    logger.info("Testing reviewer_node basic execution...")

    test_country_main = "Testlandia"
    test_mode_main = "hazards"
    test_type_main = "heatwave"
    initial_state_test = create_initial_state(country_name=test_country_main, mode_name=test_mode_main, which_name=test_type_main)
    
    mock_structured_item = StructuredDataItem(
        name="Test Heatwave Dataset Alpha", url="http://example.com/test_alpha.pdf", method_of_access="download",
        ccra_mode="hazards", ccra_type="heatwave", data_format="PDF",
        description="A test dataset about heatwave hazards in Testlandia.",
        spatial_resolution="National", temporal_coverage="2020-2023", status="new",
        country=test_country_main, country_locode="TL",
        value="Temperature data 35-45°C",
        confidence_score=None,
        raw_text_snippet=None
    )
    initial_state_test.structured_data = [mock_structured_item.model_dump()]
    initial_state_test.search_plan = [
        {"query": "Testlandia heatwave climate data", "priority": "high", "target_type": "climate_data"}
    ]
    initial_state_test.scraped_data = [
        {"url": "http://example.com/test_alpha.pdf", "status": "scraped_success", 
         "metadata": {"title": "Test Alpha Report", "scrape_method": "pdf_basic", "source_type": "pdf"}}
    ]
    initial_state_test.target_country_locode = "TL"

    if not config.OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set in .env or config. Reviewer test will use fallback/mock OpenAI client response.")
    
    logger.info(f"Testing structured_data_reviewer_node with initial state for {test_country_main}")
    updated_state_structured_test = structured_data_reviewer_node(initial_state_test)
    logger.info(f"Structured Reviewer node test executed. Suggested next step: {updated_state_structured_test.metadata.get('next_step_after_structured_review')}")
    if updated_state_structured_test.metadata.get("last_structured_review_details"):
        logger.info(f"Last structured review details: {json.dumps(updated_state_structured_test.metadata['last_structured_review_details'], indent=2)}")
    
    logger.info(f"Decision log: {json.dumps(updated_state_structured_test.decision_log, indent=2)}") 