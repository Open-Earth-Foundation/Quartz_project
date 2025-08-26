"""
AgentState definition for the LangGraph-powered CCRA Dataset Discovery Agent.
This module defines the structure for storing state across agent interactions.
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import operator
from datetime import datetime

@dataclass
class AgentState:
    """
    Central state container for the agent system.
    Contains all information that needs to be passed between nodes.
    """
    # User's original query/prompt
    prompt: str
    
    # Search planning information
    search_plan: List[Dict[str, Any]] = field(default_factory=list)
    
    # URLs discovered during research
    urls: List[Dict[str, Any]] = field(default_factory=list)
    
    # Renamed from 'documents' to 'scraped_data' to align with researcher_node
    scraped_data: List[Dict[str, Any]] = field(default_factory=list)
    
    # Extracted and structured data from documents
    structured_data: List[Dict[str, Any]] = field(default_factory=list)
    
    # Log of decisions made by the agent
    decision_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Confidence scores for various aspects of the research
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    
    # Counter for iterations to prevent infinite loops
    iteration_count: int = 0
    
    # Timestamp for when the agent started
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Metadata about the current state
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # === Fields added for country generalization ===
    target_country: Optional[str] = None
    target_country_locode: Optional[str] = None

    # === Field for tracking search limit ===
    searches_conducted_count: int = 0

    # === Field for tracking current iteration ===
    current_iteration: int = 0

    # === ADDED: API call counters ===
    api_calls_succeeded: int = 0
    api_calls_failed: int = 0

    # === CCRA: Target mode and type ===
    target_mode: Optional[str] = None  # hazards, exposure, vulnerability
    target_which: Optional[str] = None  # specific type within mode

    # === ADDED: Counter for consecutive deep dives ===
    consecutive_deep_dive_count: int = 0

    # === ADDED: URLs selected by Reviewer for extraction ===
    selected_for_extraction: Optional[List[str]] = field(default_factory=list)
    # === END ADDED ===

    # === ADDED: Counter for actions within a deep dive cycle ===
    current_deep_dive_actions_count: int = 0

    # === ADDED: City-based research support ===
    target_city: Optional[str] = None
    research_mode: str = "global"  # "global", "country", or "city"

# Define reducer functions for merging states
def reduce_list_field(field_name: str):
    """
    Create a reducer function for a specific list field in AgentState.
    This concatenates the lists from two states.
    
    Args:
        field_name: The name of the field to create a reducer for
        
    Returns:
        A function that merges the specified field from two states
    """
    def reducer(state1: AgentState, state2: AgentState) -> List[Any]:
        """Merge lists from two states."""
        list1 = getattr(state1, field_name, [])
        list2 = getattr(state2, field_name, [])
        return list1 + list2
    
    return reducer

# Dictionary for list field reducers
LIST_FIELD_REDUCERS = {
    "search_plan": reduce_list_field("search_plan"),
    "urls": reduce_list_field("urls"),
    "scraped_data": reduce_list_field("scraped_data"),
    "structured_data": reduce_list_field("structured_data"),
    "decision_log": reduce_list_field("decision_log"),
    # === ADDED: Reducer for selected_for_extraction (if needed, otherwise defaults to state2) ===
    # If we want to concatenate lists from different branches, a reducer like others would be needed.
    # For now, assuming Reviewer sets it and Extractor consumes it in a linear flow, 
    # the default behavior (value from state2, the more recent update) might be okay.
    # If parallel reviewers could select URLs, then a concatenation reducer would be essential.
    # "selected_for_extraction": reduce_list_field("selected_for_extraction"),
}

# Reducer for confidence scores - take the max value for each key
def reduce_confidence_scores(state1: AgentState, state2: AgentState) -> Dict[str, float]:
    """
    Merge confidence scores from two states by taking the maximum value for each key.
    """
    result = state1.confidence_scores.copy()
    
    for key, value in state2.confidence_scores.items():
        if key in result:
            result[key] = max(result[key], value)
        else:
            result[key] = value
            
    return result

# Reducer for iteration count - simply add them
def reduce_iteration_count(state1: AgentState, state2: AgentState) -> int:
    """
    Merge iteration counts by adding them.
    """
    return state1.iteration_count + state2.iteration_count

# Need reducers for the new fields if they should be merged
# Default behavior might be sufficient (e.g., planner sets it once)
# If merging is needed (e.g., choosing the value from the latest state):
def reduce_target_country(state1: AgentState, state2: AgentState) -> Optional[str]:
    """Use the target_country from the state that was updated more recently (state2)."""
    return state2.target_country if state2.target_country is not None else state1.target_country

def reduce_target_country_locode(state1: AgentState, state2: AgentState) -> Optional[str]:
    """Use the target_country_locode from the state that was updated more recently (state2)."""
    return state2.target_country_locode if state2.target_country_locode is not None else state1.target_country_locode

# Utility function to create a new state with default values
def create_initial_state(mode_name: str, which_name: Optional[str] = None, country_name: Optional[str] = None, city_name: Optional[str] = None, english_only_mode: bool = False) -> AgentState:
    """
    Create a new AgentState with default values for CCRA dataset discovery.

    Args:
        mode_name: The CCRA mode ('hazards', 'exposure', 'vulnerability').
        which_name: The specific type within the mode (e.g., 'heatwave', 'buildings', 'socioeconomic').
        country_name: The target country name for country-specific research (optional).
        city_name: The target city name for city-specific research (optional).
        english_only_mode: Whether to focus exclusively on English-language sources.

    Returns:
        A new AgentState instance
    """
    # Validate inputs
    if city_name and country_name:
        raise ValueError("Cannot specify both city_name and country_name. Choose either city-specific, country-specific, or global research.")
    
    # Determine research mode and create prompt
    if city_name:
        research_mode = "city"
        if which_name:
            prompt = f"CCRA Mode: {mode_name}, Type: {which_name}, City: {city_name}"
        else:
            prompt = f"CCRA Mode: {mode_name}, City: {city_name}"
        decision_log_entry = {
            "action": "init",
            "mode": mode_name,
            "which": which_name,
            "city": city_name,
            "research_mode": "city",
            "english_only_mode": english_only_mode
        }
    elif country_name:
        research_mode = "country"
        if which_name:
            prompt = f"CCRA Mode: {mode_name}, Type: {which_name}, Country: {country_name}"
        else:
            prompt = f"CCRA Mode: {mode_name}, Country: {country_name}"
        decision_log_entry = {
            "action": "init",
            "mode": mode_name,
            "which": which_name,
            "country": country_name,
            "research_mode": "country",
            "english_only_mode": english_only_mode
        }
    else:
        research_mode = "global"
        if which_name:
            prompt = f"CCRA Mode: {mode_name}, Type: {which_name}, Scope: Global"
        else:
            prompt = f"CCRA Mode: {mode_name}, Scope: Global"
        decision_log_entry = {
            "action": "init",
            "mode": mode_name,
            "which": which_name,
            "research_mode": "global",
            "english_only_mode": english_only_mode
        }

    # Optional: Implement a simple country name to LOCODE lookup here if desired
    target_locode = None # Keep it simple for now

    return AgentState(
        prompt=prompt,
        search_plan=[],
        urls=[],
        scraped_data=[],
        structured_data=[],
        decision_log=[decision_log_entry], # Log initialization with mode
        confidence_scores={},
        iteration_count=0, # Obsolete? Keep for now.
        metadata={"status": "initialized", "english_only_mode": english_only_mode, "research_mode": research_mode}, # Store mode in metadata
        target_country=country_name,
        target_mode=mode_name, # Store the CCRA mode
        target_which=which_name, # Store the specific type
        target_city=city_name, # Store the city (None for country/global mode)
        research_mode=research_mode,
        target_country_locode=target_locode,
        searches_conducted_count=0,
        current_iteration=0,
        consecutive_deep_dive_count=0,
        selected_for_extraction=[] # Initialize as empty list
    )