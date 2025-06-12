"""
# CLI Usage Examples

## City-Based Research
The agent can research GHGI data for specific cities, with sector focus:
    
    # City + specific sector research  
    python main.py --city "Kraków" --sector stationary_energy
    python main.py --city "Berlin" --sector transportation
    python main.py --city "Tokyo" --sector waste
    
    # City research with English-only sources
    python main.py --city "Kraków" --sector stationary_energy --english
    python main.py --city "Kraków" --sector afolu --english

## Country/Sector Research
Traditional country-level research requires both country and sector:

    # Country + sector research
    python main.py --country "Poland" --sector stationary_energy
    python main.py --country "Germany" --sector transportation
    
    # Country research with English-only sources
    python main.py --country "Poland" --sector afolu --english

# Available Sectors
- `afolu` - Agriculture, Forestry & Other Land Use
- `ippu` - Industrial Processes & Product Use  
- `stationary_energy` - Stationary Energy (buildings, industry, power plants)
- `transportation` - Transportation (road, rail, aviation, shipping)
- `waste` - Waste Management

# CLI Arguments

## Primary Mode Selection
- `--city CITY_NAME`: Target city for research (can be combined with --sector)
- `--country COUNTRY_NAME`: Target country for research (requires --sector)
- `--sector SECTOR_NAME`: GHGI sector to focus on (choices: afolu, ippu, stationary_energy, transportation, waste)

## Options
- `--english`: Use English-only search mode (focuses on English-language sources)
- `--log-level LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR). Default: INFO
- `--log-dir DIR`: Directory for log files. Default: logs
- `--max-iterations N`: Override maximum iterations for agent run

## Validation Rules
- Valid: City only, City+Sector, Country+Sector
- Invalid: City+Country, Country without Sector, city without sector

# Research Modes Explained

## City + Sector Mode  
When using `--city` with `--sector`:
1. Uses specialized city+sector prompt templates (e.g., `stationary_energy_city.md`)
2. Focuses queries on sector-specific city data (e.g., district heating for stationary energy)
3. Applies sector expertise to city-level research
4. Combines municipal focus with GHGI sector knowledge

## Country + Sector Mode
When using `--country` with `--sector`:
1. Uses traditional sector-specific prompts (e.g., `stationary_energy.md`)
2. Focuses on national-level GHGI data with subnational context
3. Follows established country/sector research patterns


"""
import logging
import logging.handlers
import json
from typing import Any, Dict, Optional
from dataclasses import asdict
from datetime import datetime
import os
import re
import argparse
import asyncio # Added for main_async

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig # Import RunnableConfig

import config
from agent_state import AgentState, create_initial_state
from agents.schemas import StructuredDataItem
from agents.planner import planner_node
from agents.researcher import researcher_node
from agents.reviewer import reviewer_node as raw_content_reviewer_node # RENAMED for clarity in graph
from agents.reviewer import structured_data_reviewer_node # ADDED
from agents.extractor import extractor_node
from agents.deep_diver import deep_dive_processor_node

# --- Setup Logging ---
def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """
    Configure logging with both file and console handlers.
    File handler uses UTF-8 encoding to handle Unicode characters.
    Console handler is configured to handle encoding errors gracefully.
    """
    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_dir, f"ghgi_agent_{timestamp}.log")
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set root logger level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(process)d - %(threadName)s - %(levelname)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # File handler with UTF-8 encoding
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler with error handling for encoding issues
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    
    # Set console handler encoding to handle Unicode gracefully
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            # If reconfigure fails, we'll rely on the errors='replace' in the handler
            pass
    
    # Override the emit method to handle encoding errors gracefully
    original_emit = console_handler.emit
    def safe_emit(record):
        try:
            original_emit(record)
        except UnicodeEncodeError:
            # If we get a Unicode error, try to encode the message safely
            try:
                if hasattr(record, 'msg') and isinstance(record.msg, str):
                    record.msg = record.msg.encode('ascii', errors='replace').decode('ascii')
                original_emit(record)
            except Exception:
                # Last resort: skip this log message
                pass
    
    console_handler.emit = safe_emit
    root_logger.addHandler(console_handler)
    
    # Log the setup completion
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured. File: {log_filename}, Level: {log_level}")
    logger.info(f"Console encoding configured with error handling for Unicode characters")

# Initialize logger after setup function is defined
logger = logging.getLogger(__name__)

# Reviewer stub is removed as we now use the actual reviewer_node

# --- Graph Definition ---
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("planner", planner_node)
workflow.add_node("researcher", researcher_node)
workflow.add_node("raw_content_reviewer", raw_content_reviewer_node) # ADDED (using existing reviewer_node)
workflow.add_node("extractor", extractor_node)
workflow.add_node("structured_reviewer", structured_data_reviewer_node) # ADDED
workflow.add_node("deep_diver", deep_dive_processor_node)

# Define edges
workflow.set_entry_point("planner")
workflow.add_edge("planner", "researcher")
workflow.add_edge("researcher", "raw_content_reviewer") # MODIFIED: Researcher -> RawContentReviewer
workflow.add_edge("extractor", "structured_reviewer") # MODIFIED: Extractor -> StructuredReviewer

# --- Conditional routing after Raw Content Review ---
def route_after_raw_content_review(state: AgentState) -> str:
    action = state.metadata.get("next_step_after_review", "end").lower() # Key set by raw_content_reviewer_node
    logger.info(f"Routing after raw_content_reviewer: Action='{action}'. Iter={state.current_iteration}.")

    if action == "proceed_to_extraction":
        if not state.selected_for_extraction:
            logger.warning("Raw content reviewer suggested 'proceed_to_extraction' but selected no documents. Routing to 'refine_plan' as fallback.")
            # Optionally, log this decision more formally in state.decision_log if needed
            return "planner"
        logger.info("Raw content reviewer suggested: proceed_to_extraction. Routing to extractor.")
        return "extractor"
    elif action == "refine_plan":
        logger.info("Raw content reviewer suggested: refine_plan. Routing to planner.")
        return "planner"
    elif action == "end":
        logger.info("Raw content reviewer suggested: end. Routing to END.")
        return END
    else:
        logger.warning(f"Unknown action '{action}' from raw_content_reviewer. Defaulting to END.")
        return END

workflow.add_conditional_edges(
    "raw_content_reviewer",
    route_after_raw_content_review,
    {
        "extractor": "extractor",
        "planner": "planner",
        END: END
    }
)

# --- Conditional routing after Structured Data Review ---
# This function is similar to the previous route_after_review, now specific to structured_reviewer
def route_after_structured_review(state: AgentState) -> str:
    action = state.metadata.get("next_step_after_structured_review", "reject").lower() # Key set by structured_data_reviewer_node
    consecutive_deep_dives = state.consecutive_deep_dive_count

    logger.info(f"Routing after structured_reviewer: Action='{action}'. Iter={state.current_iteration}. Consecutive Deep Dives={consecutive_deep_dives}")

    # Iteration limit check (applies to overall process)
    if state.current_iteration >= config.MAX_ITERATIONS:
        logger.warning(f"Max iterations ({config.MAX_ITERATIONS}) reached. Forcing END route from structured_reviewer.")
        return END

    if action == "deep_dive":
        if consecutive_deep_dives >= config.MAX_DEEP_DIVES:
            logger.warning(f"Max consecutive deep dives ({config.MAX_DEEP_DIVES}) reached. Routing to END instead of deep_dive from structured_reviewer.")
            return END
        else:
            logger.info(f"Structured reviewer suggested: deep_dive. Routing to deep_diver. Current consecutive deep dives: {consecutive_deep_dives}")
            # Note: State mutation (incrementing counters) should happen in deep_dive_processor_node, not here
            return "deep_diver"
    else:
        # Note: Resetting consecutive_deep_dive_count should happen in the respective nodes, not here
        pass

    if action == "accept":
        logger.info("Structured reviewer suggested: accept. Routing to END.")
        return END
    elif action == "reject":
        logger.info("Structured reviewer suggested: reject. Routing to END.")
        return END
    elif action == "refine_plan":
        logger.info("Structured reviewer suggested: refine_plan. Routing to planner.")
        return "planner"
    else:
        logger.warning(f"Unknown action '{action}' from structured_reviewer. Defaulting to END.")
        return END

workflow.add_conditional_edges(
    "structured_reviewer", # Source node
    route_after_structured_review, # Routing function
    { # Mapping from routing function's return string to next node name
        "planner": "planner",
        "deep_diver": "deep_diver",
        END: END
    }
)

# --- Conditional routing after Deep Dive Processor ---
def route_after_deep_dive(state: AgentState) -> str:
    action_info = state.metadata.get("deep_dive_action", {})
    action_type = action_info.get("action_type") # This could be None if not set

    logger.debug(f"Routing after deep_dive_processor. Action type: '{action_type}', Details: {action_info}")

    if action_type == "scrape":
        logger.info(f"Deep diver action is 'scrape'. Routing to researcher node.")
        return "researcher"  # Assuming the node is named "researcher"
    elif action_type == "crawl":
        logger.info(f"Deep diver action is 'crawl'. Routing to researcher node.")
        return "researcher"  # Route crawl to researcher node as well
    elif action_type == "terminate_deep_dive":
        logger.info("Deep diver action is 'terminate_deep_dive'. Routing to structured_reviewer node.")
        return "structured_reviewer"  # Assuming the node is named "structured_reviewer"
    else:
        if action_type is None:
            logger.warning("Deep dive action_type is None. Defaulting to structured_reviewer node.")
        else:
            logger.warning(f"Unknown deep_dive_action_type: '{action_type}'. Defaulting to structured_reviewer node.")
        return "structured_reviewer"  # Fallback to structured_reviewer

workflow.add_conditional_edges(
    "deep_diver",
    route_after_deep_dive,
    {
        "researcher": "researcher",
        "structured_reviewer": "structured_reviewer" # MODIFIED
        # No direct END here, termination of deep dive cycle leads back to structured_reviewer.
    }
)

# LangSmith tracing is automatically enabled if LANGCHAIN_TRACING_V2, LANGCHAIN_ENDPOINT,
# LANGCHAIN_API_KEY, and LANGCHAIN_PROJECT environment variables are set.
# Ensure `langsmith` is installed (see requirements.txt).
logger.info("Compiling the research workflow graph.")
# Compile the workflow graph
ghgi_graph = workflow.compile()
logger.info("GHGI Agent graph compiled successfully.")

# --- Save Results Function ---
def save_results_to_json(state: AgentState, output_dir: str = "runs") -> Optional[str]:
    """
    Save agent results to a JSON file if the final structured review action is 'accept'.
    Supports both city and country modes.
    """
    final_structured_review_action = state.metadata.get("next_step_after_structured_review", "not_set")

    if not final_structured_review_action == "accept":
        logger.info(f"Skipping save: final structured review action was '{final_structured_review_action}', not 'accept'.")
        return None

    try:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate filename based on research mode
        research_mode = state.metadata.get("research_mode", "unknown")
        if research_mode == "city":
            # City mode filename
            city_name_sanitized = re.sub(r'[^\w\-_\.]', '_', state.target_city or "UnknownCity")
            filename = f"results_city_{city_name_sanitized}_{timestamp}.json"
        else:
            # Country mode filename
            country_name_sanitized = re.sub(r'[^\w\-_\.]', '_', state.target_country or "UnknownCountry")
            sector_sanitized = re.sub(r'[^\w\-_\.]', '_', state.target_sector or "UnknownSector")
            filename = f"results_{country_name_sanitized}_{sector_sanitized}_{timestamp}.json"
        
        filepath = os.path.join(output_dir, filename)

        # Data to save - focus on accepted items and summary
        data_to_save = {
            "research_mode": research_mode,
            "target_country": state.target_country,
            "target_country_locode": state.target_country_locode,
            "target_sector": state.target_sector,
            "target_city": state.target_city,
            "start_time": state.start_time,
            "end_time": datetime.now().isoformat(),
            "total_iterations": state.current_iteration,
            "final_structured_review_action": final_structured_review_action,
            "final_confidence": state.metadata.get("final_review_confidence_assessment"),
            "structured_data_items_count": len(state.structured_data),
            "structured_data": state.structured_data,
            "decision_log": state.decision_log,
            "search_plan_summary": state.search_plan
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        logger.info(f"Results successfully saved to: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to save results to JSON: {e}", exc_info=True)
        return None

# --- Main Execution Logic ---
async def run_agent(country_name: Optional[str] = None, sector_name: Optional[str] = None, city_name: Optional[str] = None, english_only_mode: bool = False, cli_config_overrides: Optional[Dict[str, Any]] = None) -> AgentState:
    """
    Initializes and runs the agent for either country/sector or city research.
    Applies temporary config overrides if provided either directly or from CLI.
    """
    initial_config_values = {}
    if cli_config_overrides: # Apply CLI overrides first
        for key, value in cli_config_overrides.items():
            if hasattr(config, key):
                initial_config_values[key] = getattr(config, key)
                setattr(config, key, value)
                logger.info(f"Applying CLI override: config.{key} = {value}")
            else:
                logger.warning(f"Config key '{key}' not found in config.py, cannot apply CLI override.")

    # Create initial state based on mode
    if city_name:
        initial_state = create_initial_state(city_name=city_name, sector_name=sector_name, english_only_mode=english_only_mode)
        if sector_name:
            logger.info(f"Starting agent for city: {city_name}, sector: {sector_name}, English-only mode: {english_only_mode}")
        else:
            logger.info(f"Starting agent for city: {city_name}, English-only mode: {english_only_mode}")
    else:
        initial_state = create_initial_state(country_name=country_name, sector_name=sector_name, english_only_mode=english_only_mode)
        logger.info(f"Starting agent for country: {country_name}, Sector: {sector_name}, English-only mode: {english_only_mode}")
    
    logger.debug(f"Initial state passed to graph.ainvoke: {initial_state}")
    
    if not config.OPENROUTER_API_KEY or not config.FIRECRAWL_API_KEY:
        logger.error("API keys for OpenRouter or Firecrawl are not set. Agent may fail.")
    
    logger.info(f"Invoking graph for state: {initial_state.prompt}...")
    raw_final_state_dict: Any = None # Initialize
    # Define the configuration for the invocation, including the recursion limit
    invocation_config = RunnableConfig(recursion_limit=200) # Increased from 100 to 200

    logger.info(f"DEBUG: ID of initial_state BEFORE ainjection: {id(initial_state)}")
    logger.info(f"DEBUG: current_iteration of initial_state BEFORE ainjection: {initial_state.current_iteration}")

    try:
        raw_final_state_dict = await ghgi_graph.ainvoke(initial_state, config=invocation_config)
        # ---- ADD DEBUG ----
        logger.info(f"DEBUG_MAIN_RUN_AGENT: raw_final_state_dict from ainjection type: {type(raw_final_state_dict)}")
        if isinstance(raw_final_state_dict, dict):
            logger.info(f"DEBUG_MAIN_RUN_AGENT: current_iteration in raw_final_state_dict: {raw_final_state_dict.get('current_iteration')}")
            # Log more fields from the dict to understand its structure
            loggable_dict = {k: v for k, v in raw_final_state_dict.items() if k not in ['scraped_data', 'structured_data']} # Avoid logging large fields
            logger.info(f"DEBUG_MAIN_RUN_AGENT: raw_final_state_dict (partial): {loggable_dict}")
        elif hasattr(raw_final_state_dict, 'current_iteration'): # If it's already an AgentState object
            logger.info(f"DEBUG_MAIN_RUN_AGENT: current_iteration in raw_final_state_dict (object): {raw_final_state_dict.current_iteration}")
        # ---- END DEBUG ----
    except Exception as e:
        logger.error(f"CRITICAL: Graph execution failed. Error: {type(e).__name__} - {e}", exc_info=True)
        logger.error("This can be expected in CLI test scenarios with dummy API keys if agent nodes attempt to use them.")
        # Fallback to initial_state to allow summary generation and graceful exit
        from dataclasses import asdict # Ensure asdict is available
        raw_final_state_dict = asdict(initial_state) 
    
    logger.info(f"Graph ainvoke finished or was bypassed due to error. Result type: {type(raw_final_state_dict)}")
    logger.debug(f"Raw result from graph.ainvoke: {raw_final_state_dict}")
    logger.info(f"DEBUG: ID of initial_state AFTER ainjection: {id(initial_state)}")
    if isinstance(raw_final_state_dict, AgentState):
        logger.info(f"DEBUG: ID of raw_final_state_dict (AgentState) AFTER ainjection: {id(raw_final_state_dict)}")
        logger.info(f"DEBUG: current_iteration of raw_final_state_dict (AgentState) AFTER ainjection: {raw_final_state_dict.current_iteration}")
    elif isinstance(raw_final_state_dict, dict):
        logger.info(f"DEBUG: raw_final_state_dict is a dict. Iteration if present: {raw_final_state_dict.get('current_iteration')}")

    # ensure raw_final_state_dict is a dict
    if not isinstance(raw_final_state_dict, dict):
        logger.error(f"Could not extract or reconstruct AgentState from graph output. Output was: {raw_final_state_dict}")
        if city_name:
            final_state = create_initial_state(city_name=city_name, sector_name=sector_name, english_only_mode=english_only_mode)
        else:
            final_state = create_initial_state(country_name=country_name, sector_name=sector_name, english_only_mode=english_only_mode)
    else:
        final_state = AgentState(**raw_final_state_dict)

    # Log completion message based on mode
    if city_name:
        if sector_name:
            logger.info(f"Agent run completed for city: {city_name}, sector: {sector_name}.")
        else:
            logger.info(f"Agent run completed for city: {city_name}.")
    else:
        logger.info(f"Agent run completed for country: {country_name}, Sector: {sector_name}.")
    
    if isinstance(final_state, AgentState):
        logger.info(f"Final decision log: {json.dumps(final_state.decision_log, indent=2)}")
    else:
        logger.warning(f"Agent run resulted in unexpected state type: {type(final_state)}")
    
    if initial_config_values:
        for key, value in initial_config_values.items():
            setattr(config, key, value)
            logger.info(f"Restored config: {key} = {getattr(config, key)}")
    return final_state

async def main_async(args, cli_config_overrides: Optional[Dict[str, Any]] = None):
    """Asynchronous main function to run the agent and print summary."""
    # Determine which mode to run in
    if hasattr(args, 'city') and args.city:
        # City mode (with optional sector)
        sector_name = getattr(args, 'sector', None)
        final_state = await run_agent(city_name=args.city, sector_name=sector_name, english_only_mode=args.english, cli_config_overrides=cli_config_overrides)
    else:
        # Country mode (sector is required)
        final_state = await run_agent(country_name=args.country, sector_name=args.sector, english_only_mode=args.english, cli_config_overrides=cli_config_overrides)
    
    # Print summary based on mode
    print("\n--- Agent Run Summary ---")
    research_mode = final_state.metadata.get("research_mode", "unknown")
    if research_mode == "city":
        print(f"Target City:             {final_state.target_city}")
        if final_state.target_sector:
            print(f"Target Sector:           {final_state.target_sector}")
            print(f"Research Mode:           City + Sector-based")
        else:
            print(f"Research Mode:           City-based (all sectors)")
    else:
        print(f"Target Country:          {final_state.target_country}")
        print(f"Target Sector:           {final_state.target_sector}")
        print(f"Research Mode:           Country/Sector-based")
    
    print(f"English-only Mode:       {final_state.metadata.get('english_only_mode', False)}")
    print(f"LOCODE:                  {final_state.target_country_locode}")
    print(f"Start Time:              {final_state.start_time}")
    print(f"End Time:                {datetime.now().isoformat()}")
    print(f"Total Iterations:        {final_state.current_iteration}")
    print(f"Searches Conducted:      {final_state.searches_conducted_count}")
    
    # Reviewer output
    final_review_action = final_state.metadata.get("next_step_after_review", "N/A") # This is raw review
    final_structured_review_action = final_state.metadata.get("next_step_after_structured_review", "N/A") # ADDED
    final_confidence = final_state.metadata.get("final_review_confidence_assessment", "N/A") # This might be from structured
    
    # Get overall confidence from structured review details if available
    structured_review_details = final_state.metadata.get("last_structured_review_details", {})
    overall_confidence_structured = structured_review_details.get("overall_confidence", "N/A")

    print(f"Final Raw Review Action:   {final_review_action}") # Clarify
    print(f"Final Structured Review Action: {final_structured_review_action}") # ADDED
    print(f"Final Structured Review Confidence: {overall_confidence_structured}") # Clarify

    # Data output
    num_structured_items = len(final_state.structured_data)
    print(f"Structured Items Found:  {num_structured_items}")

    if final_structured_review_action == "accept" and num_structured_items > 0: # MODIFIED to check structured review
        output_file = save_results_to_json(final_state, config.OUTPUT_DIR)
        if output_file:
            print(f"Results Saved To:        {output_file}")
        else:
            print("Results Save Skipped:    Final action was not 'accept' or no data.")
    else:
        print("Results Save Skipped:    Final action was not 'accept' or no structured data.")

    print("\n--- Key Decision Log Entries ---")
    for log_entry in final_state.decision_log[-5:]:
        print(f"- {log_entry.get('timestamp', 'N/A')} [{log_entry.get('agent', 'System')}] {log_entry.get('action', 'log')}: {log_entry.get('message', '')[:100]}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the GHGI Dataset Discovery Agent.")
    
    # Primary mode selection
    parser.add_argument("--city", type=str, help="The target city name for research. Use quotes for multi-word names like 'San Francisco'. Can be combined with --sector for sector-specific city research.")
    parser.add_argument("--country", type=str, help="The target country name for the research. Use quotes for multi-word names or separate words will be joined automatically. Cannot be used with --city.")
    parser.add_argument("--sector", type=str, choices=['afolu', 'ippu', 'stationary_energy', 'transportation', 'waste'], help="The target GHGI sector. Can be used with either --city or --country.")
    
    parser.add_argument("--english", action="store_true", help="Use English-only search mode. This will focus exclusively on English-language sources and documentation.")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Set the logging level.")
    parser.add_argument("--log-dir", type=str, default="logs", help="Directory to store log files.")
    parser.add_argument("--max-iterations", type=int, help="Override the maximum number of iterations for the agent run.")
    
    # Parse known args first to handle multi-word city/country names
    known_args, unknown_args = parser.parse_known_args()
    
    # Validate argument combinations
    if not known_args.city and not known_args.country:
        parser.error("Either --city or --country must be provided.")
    
    if known_args.city and known_args.country:
        parser.error("Cannot use both --city and --country. Choose either city mode or country mode.")
    
    if known_args.country and not known_args.sector:
        parser.error("--country requires --sector to be specified.")
    
    # If there are unknown args, they're likely part of a multi-word name
    if unknown_args:
        logger_temp = logging.getLogger(__name__)
        if known_args.city:
            # Join the city name with unknown args
            city_parts = [known_args.city] + unknown_args
            known_args.city = ' '.join(city_parts)
            logger_temp.info(f"Detected multi-word city name: '{known_args.city}' (joined from {city_parts})")
        elif known_args.country:
            # Join the country name with unknown args
            country_parts = [known_args.country] + unknown_args
            known_args.country = ' '.join(country_parts)
            logger_temp.info(f"Detected multi-word country name: '{known_args.country}' (joined from {country_parts})")
    
    args = known_args

    # Setup logging with UTF-8 encoding and error handling
    setup_logging(log_level=args.log_level, log_dir=args.log_dir)
    
    # Now we can safely use the logger
    if args.city:
        if args.sector:
            logger.info(f"Starting GHGI Agent for city: {args.city}, sector: {args.sector} with log level: {args.log_level}")
        else:
            logger.info(f"Starting GHGI Agent for city: {args.city} (all sectors) with log level: {args.log_level}")
    else:
        logger.info(f"Starting GHGI Agent for country: {args.country}, sector: {args.sector} with log level: {args.log_level}")
    
    if args.english:
        logger.info("English-only mode enabled: Will focus exclusively on English-language sources")

    # Handle max_iterations override
    config_overrides = {}
    if args.max_iterations is not None:
        config_overrides["MAX_ITERATIONS"] = args.max_iterations
        logger.info(f"CLI override: MAX_ITERATIONS will be set to {args.max_iterations}")

    # For CLI execution, we need to run the async function
    asyncio.run(main_async(args, config_overrides)) 