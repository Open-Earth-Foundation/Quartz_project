import logging
from typing import Dict, Any
from pathlib import Path
import json # Added for parsing JSON response
import traceback # Import traceback
import asyncio # Add asyncio for delays
import re # Add re for URL pattern matching

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError # Added Pydantic

import config

logger = logging.getLogger(__name__)

RELEVANCE_CHECK_PROMPT_PATH = Path(__file__).parent / "prompts" / "relevance_check_prompt.md"

class RelevanceCheckError(Exception):
    """Custom exception for relevance check failures."""
    pass

# Define the Pydantic model for structured output
class RelevanceCheckOutput(BaseModel):
    is_relevant: bool = Field(description="True if the search result is relevant, False otherwise.")
    reason: str = Field(description="A brief explanation for the relevance decision")

def _parse_ccra_context(target_sector: str) -> tuple[str, str]:
    """Parse CCRA context from target_sector parameter.
    
    Args:
        target_sector: String like "hazards heatwave" or "emissions transportation"
        
    Returns:
        Tuple of (ccra_mode, ccra_type)
    """
    parts = target_sector.lower().split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    elif len(parts) == 1:
        return parts[0], "unknown"
    else:
        return "unknown", "unknown"

def _generate_system_prompt(ccra_mode: str, ccra_type: str, target_country: str) -> str:
    """Generate appropriate system prompt based on CCRA mode and type."""
    
    if ccra_mode == "hazards":
        if ccra_type == "heatwave":
            return (
                f"You are a climate data relevance assessment assistant. "
                f"Your task is to determine if the provided web search result is relevant for finding heatwave hazard data, temperature extremes, and heat stress indicators for {target_country}. "
                f"Focus on: daily maximum temperature data, temperature percentiles, heat wave indices, thermal stress indicators, climate projections, meteorological temperature records, and official climate datasets. "
                f"Accept sources that provide temperature time series, heat wave frequency/duration data, thermal comfort indices, or climate risk assessment data. "
                f"You must respond with a JSON object that strictly adheres to the following Pydantic schema: {RelevanceCheckOutput.model_json_schema()}. "
                f"Ensure your output is a single, valid JSON object and nothing else."
            )
        else:
            # Generic hazards prompt
            return (
                f"You are a climate data relevance assessment assistant. "
                f"Your task is to determine if the provided web search result is relevant for finding {ccra_type} hazard data and climate risk indicators for {target_country}. "
                f"Focus on: climate datasets, meteorological observations, hazard indices, climate projections, and official climate risk assessment data. "
                f"You must respond with a JSON object that strictly adheres to the following Pydantic schema: {RelevanceCheckOutput.model_json_schema()}. "
                f"Ensure your output is a single, valid JSON object and nothing else."
            )
    elif ccra_mode == "exposure":
        return (
            f"You are a climate exposure data relevance assessment assistant. "
            f"Your task is to determine if the provided web search result is relevant for finding exposure data related to {ccra_type} for {target_country}. "
            f"Focus on: population data, infrastructure inventories, asset databases, land use data, building stocks, and socioeconomic datasets. "
            f"You must respond with a JSON object that strictly adheres to the following Pydantic schema: {RelevanceCheckOutput.model_json_schema()}. "
            f"Ensure your output is a single, valid JSON object and nothing else."
        )
    elif ccra_mode == "vulnerability":
        return (
            f"You are a climate vulnerability data relevance assessment assistant. "
            f"Your task is to determine if the provided web search result is relevant for finding vulnerability data related to {ccra_type} for {target_country}. "
            f"Focus on: socioeconomic indicators, adaptive capacity metrics, sensitivity measures, demographic data, and vulnerability indices. "
            f"You must respond with a JSON object that strictly adheres to the following Pydantic schema: {RelevanceCheckOutput.model_json_schema()}. "
            f"Ensure your output is a single, valid JSON object and nothing else."
        )
    else:
        # Default to emissions/GHG mode for backward compatibility
        return (
            f"You are a data relevance assessment assistant. "
            f"Your task is to determine if the provided web search result is relevant for finding activity-level greenhouse gas data, emissions statistics, or sector-specific activity data for {target_country}. "
            f"Focus on: fuel use, production volumes, transport statistics, agricultural output, energy balance data, and official government statistics that can be converted into emissions. "
            f"You must respond with a JSON object that strictly adheres to the following Pydantic schema: {RelevanceCheckOutput.model_json_schema()}. "
            f"Ensure your output is a single, valid JSON object and nothing else."
        )

def load_relevance_check_prompt_template() -> str:
    """Loads the relevance check prompt template from file."""
    try:
        if RELEVANCE_CHECK_PROMPT_PATH.exists():
            return RELEVANCE_CHECK_PROMPT_PATH.read_text(encoding="utf-8")
        else:
            logger.error(f"Relevance check prompt file not found: {RELEVANCE_CHECK_PROMPT_PATH}")
            # Fallback prompt (though system prompt will define JSON structure)
            return "URL: {url}\nTitle: {title}\nSnippet: {snippet}\n\nBased on the above for {target_country}, assess its relevance for finding activity-level greenhouse gas data or emissions statistics."
    except Exception as e:
        logger.error(f"Error loading relevance check prompt file {RELEVANCE_CHECK_PROMPT_PATH}: {e}")
        return "URL: {url}\nTitle: {title}\nSnippet: {snippet}\n\nBased on the above for {target_country}, assess its relevance for finding activity-level greenhouse gas data or emissions statistics." # Fallback updated for GHG focus

def fallback_relevance_check(search_result: Dict[str, Any], target_country: str, target_sector: str) -> RelevanceCheckOutput:
    """Fallback relevance scoring based on URL patterns and keywords when LLM is unavailable."""
    url = search_result.get("url", "")
    title = search_result.get("title", "")
    snippet = search_result.get("snippet", "")
    
    # Combine all text for analysis
    combined_text = f"{url} {title} {snippet}".lower()
    
    # Parse CCRA context
    ccra_mode, ccra_type = _parse_ccra_context(target_sector)
    
    # Define patterns based on CCRA mode
    if ccra_mode == "hazards" and ccra_type == "heatwave":
        # High-relevance patterns for heatwave hazard data
        high_relevance_patterns = [
            r'temperature.*data', r'heat.*wave', r'thermal.*stress', r'temperature.*extreme',
            r'daily.*temperature', r'maximum.*temperature', r'tmax', r'temperature.*percentile',
            r'heat.*index', r'wbgt', r'utci', r'apparent.*temperature',
            r'climate.*data', r'meteorological.*data', r'weather.*data'
        ]
        
        # Medium-relevance patterns
        medium_relevance_patterns = [
            r'temperature', r'heat', r'thermal', r'climate', r'weather',
            r'dataset', r'statistics', r'data.*portal', r'gridded.*data',
            r'reanalysis', r'era5', r'ncep', r'noaa', r'nasa'
        ]
        
        pattern_type = "heatwave hazard"
        
    elif ccra_mode == "hazards":
        # Generic hazards patterns
        high_relevance_patterns = [
            r'climate.*data', r'hazard.*data', r'meteorological.*data', r'weather.*data',
            r'climate.*projection', r'climate.*scenario', r'climate.*risk'
        ]
        
        medium_relevance_patterns = [
            r'climate', r'weather', r'hazard', r'dataset', r'statistics',
            r'data.*portal', r'meteorological', r'environmental.*data'
        ]
        
        pattern_type = f"{ccra_type} hazard"
        
    elif ccra_mode == "exposure":
        # Exposure data patterns
        high_relevance_patterns = [
            r'population.*data', r'infrastructure.*data', r'building.*stock', r'asset.*data',
            r'land.*use', r'demographic.*data', r'census.*data', r'exposure.*data'
        ]
        
        medium_relevance_patterns = [
            r'population', r'infrastructure', r'building', r'asset', r'demographic',
            r'census', r'exposure', r'dataset', r'statistics'
        ]
        
        pattern_type = f"{ccra_type} exposure"
        
    elif ccra_mode == "vulnerability":
        # Vulnerability data patterns
        high_relevance_patterns = [
            r'vulnerability.*data', r'socioeconomic.*data', r'adaptive.*capacity', r'sensitivity.*data',
            r'vulnerability.*index', r'social.*data', r'economic.*data'
        ]
        
        medium_relevance_patterns = [
            r'vulnerability', r'socioeconomic', r'adaptive', r'sensitivity', r'social',
            r'economic', r'dataset', r'statistics', r'index'
        ]
        
        pattern_type = f"{ccra_type} vulnerability"
        
    else:
        # Default to GHG/emissions patterns for backward compatibility
        high_relevance_patterns = [
            r'emissions.*data', r'ghg.*data', r'greenhouse.*gas', r'emissions.*portal',
            r'unfccc', r'crf', r'emissions.*inventory', r'activity.*data',
            r'fuel.*consumption', r'production.*volume', r'transport.*statistics',
            r'agricultural.*output', r'energy.*balance', r'statistics.*portal',
            r'government.*statistics', r'official.*data', r'downloadable.*data'
        ]
        
        medium_relevance_patterns = [
            r'emissions', r'ghg', r'greenhouse', r'gas', r'fuel',
            r'environmental.*data', r'statistical.*data', r'research.*data',
            r'scientific.*data', r'dataset', r'statistics', r'data.*portal'
        ]
        
        pattern_type = "GHG/emissions"
    
    # Low-relevance (exclude) patterns - common across all modes
    exclude_patterns = [
        r'news', r'blog', r'social.*media', r'forum', r'wiki',
        r'commercial', r'advertisement', r'shopping', r'product'
    ]
    
    # Check for exclusions first
    for pattern in exclude_patterns:
        if re.search(pattern, combined_text):
            return RelevanceCheckOutput(
                is_relevant=False,
                reason=f"Excluded due to pattern: {pattern}"
            )
    
    # Check for high relevance
    high_matches = sum(1 for pattern in high_relevance_patterns if re.search(pattern, combined_text))
    if high_matches >= 2:
        return RelevanceCheckOutput(
            is_relevant=True,
            reason=f"High relevance: {high_matches} {pattern_type} patterns matched"
        )
    
    # Check for medium relevance
    medium_matches = sum(1 for pattern in medium_relevance_patterns if re.search(pattern, combined_text))
    if medium_matches >= 2 or high_matches >= 1:
        return RelevanceCheckOutput(
            is_relevant=True,
            reason=f"Medium relevance: {medium_matches} {pattern_type} patterns + {high_matches} high patterns"
        )
    
    # Default to not relevant
    return RelevanceCheckOutput(
        is_relevant=False,
        reason=f"No significant {pattern_type} patterns found"
    )

async def check_url_relevance_async(search_result: Dict[str, Any], target_country: str, target_sector: str, client: AsyncOpenAI, delay_seconds: float = 0.5) -> RelevanceCheckOutput:
    """Check if a URL and its snippet are relevant using an LLM with structured JSON output. Returns a RelevanceCheckOutput object."""
    raw_content = "<not_yet_fetched>" # Initialize for error logging
    url = search_result.get("url") # Get URL early for logging in error cases

    # Add delay to prevent rate limiting
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)

    try:
        snippet = search_result.get("snippet")
        title = search_result.get("title")

        if not url or not snippet:
            logger.warning(f"Missing URL or snippet for relevance check of item: {search_result.get('title', 'N/A')}. Skipping.")
            return RelevanceCheckOutput(is_relevant=False, reason="Missing URL or snippet")

        if not config.RELEVANCE_CHECK_MODEL:
            logger.warning("RELEVANCE_CHECK_MODEL not configured. Skipping relevance check, assuming relevant by default.")
            return RelevanceCheckOutput(is_relevant=True, reason="RELEVANCE_CHECK_MODEL not configured, assumed relevant")

        # Determine CCRA mode from target_sector parameter
        ccra_mode, ccra_type = _parse_ccra_context(target_sector)
        
        prompt_template = load_relevance_check_prompt_template()
        current_user_prompt = prompt_template.format(
            target_country=target_country,
            sector=target_sector,
            url=url,
            title=title,
            snippet=snippet
        )

        # Generate context-appropriate system prompt based on CCRA mode
        system_prompt = _generate_system_prompt(ccra_mode, ccra_type, target_country)

        logger.debug(f"Checking relevance for URL: {url} with model: {config.RELEVANCE_CHECK_MODEL} using JSON mode.")
        response = await client.chat.completions.create( # type: ignore
            model=config.RELEVANCE_CHECK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": current_user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        raw_content = response.choices[0].message.content
        if not raw_content:
            logger.error(f"Relevance check for {url} returned empty content.")
            return RelevanceCheckOutput(is_relevant=False, reason="LLM returned empty content for relevance check")

        logger.debug(f"Relevance check for {url}: Raw LLM response: '{raw_content}'")
        
        # Add validation for empty JSON objects
        if raw_content.strip() in ['{}', '{"}']:
            logger.warning(f"LLM returned empty JSON object for {url}. Using fallback relevance check.")
            return fallback_relevance_check(search_result, target_country, target_sector)
        
        try:
            parsed_output = RelevanceCheckOutput.model_validate_json(raw_content)
        except ValidationError as validation_error:
            logger.warning(f"Pydantic validation failed for {url}: {validation_error}. Raw content: '{raw_content}'. Using fallback.")
            return fallback_relevance_check(search_result, target_country, target_sector)
        except Exception as validation_error:
            logger.warning(f"Failed to validate LLM response for {url}: {validation_error}. Raw content: '{raw_content}'. Using fallback.")
            return fallback_relevance_check(search_result, target_country, target_sector)
        
        logger.info(f"Relevance check for {url}: Relevant: {parsed_output.is_relevant}, Reason: '{parsed_output.reason}'")
        return parsed_output
    
    except KeyError as e_key:
        logger.error(f"KeyError during relevance check for URL {url}. Key: {e_key}. Traceback: {traceback.format_exc()}")
        # Re-raise specific errors if researcher.py is expected to handle them for retry or specific flow control.
        # For now, returning a "False" RelevanceCheckOutput to ensure function signature is met.
        # Consider if specific exceptions should still be raised.
        return RelevanceCheckOutput(is_relevant=False, reason=f"KeyError during processing: {e_key}")
    except json.JSONDecodeError as e_json:
        logger.error(f"JSONDecodeError parsing relevance check response for URL {url}. Raw content: '{raw_content}'. Error: {e_json}", exc_info=True)
        return RelevanceCheckOutput(is_relevant=False, reason=f"JSONDecodeError: {e_json}")
    except Exception as e:
        error_str = str(e)
        # Check if it's a rate limiting error
        if "429" in error_str or "rate limit" in error_str.lower():
            logger.warning(f"Rate limit hit for URL {url}. Using fallback relevance check.")
            return fallback_relevance_check(search_result, target_country, target_sector)
        else:
            logger.error(f"Unexpected error during relevance check for URL {url} with model {config.RELEVANCE_CHECK_MODEL}: {e}", exc_info=True)
            # Use fallback for any other errors too
            return fallback_relevance_check(search_result, target_country, target_sector)