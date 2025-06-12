"""
Data Extraction Agent - Responsible for parsing and structuring data from documents.

This agent:
1. Extracts text from various document formats ( HTML, etc.)
2. Parses tables and structured data
3. Organizes information according to the GHGI sector schema
4. Produces standardized JSON outputs for consistent processing
"""
import logging
import json
from typing import Dict, List, Any, Optional, Union
import re
import os
from pathlib import Path
from pydantic import BaseModel, Field
from dataclasses import asdict
from openai.types.chat import ChatCompletionMessageParam

# Set up logging
logger = logging.getLogger(__name__)

# Import project modules
import config
from agent_state import AgentState
from agents.utils import needs_advanced_scraping

# Define the data structure for extracted datasets using Pydantic
class ExtractorOutputSchema(BaseModel):
    """Pydantic schema definition for structured GHGI dataset information extracted by the LLM."""
    name: Optional[str] = Field(None, description="Name of the dataset or report found in the content.")
    url: Optional[str] = Field(None, description="Source URL where the data was found (should match the input document's URL).")
    method_of_access: Optional[str] = Field(None, description="How the data might be accessed (e.g., downloadable file mentioned, API documentation seen, embedded table, web interface query).")
    sector: Optional[Union[str, List[str]]] = Field(None, description="Primary GHGI sector classification (Energy, IPPU, AFOLU, Waste) relevant to the content.")
    subsector: Optional[Union[str, List[str]]] = Field(None, description="Specific subsector within the main sector, if identifiable.")
    data_format: Optional[Union[str, List[str]]] = Field(None, description="Format of the data if mentioned or implied (e.g., PDF, Excel, CSV, database, specific table format).")
    description: Optional[str] = Field(None, description="A concise description summarizing the dataset's content, provider (if mentioned), time period covered (if found), and update frequency (if mentioned).")
    granularity: Optional[Union[str, List[str]]] = Field(None, description="Geographic specificity if mentioned (e.g., national, regional, municipal for the target country).")
    country: Optional[str] = Field(None, description="Country that the data covers (should match target_country).")
    country_locode: Optional[str] = Field(None, description="UN LOCODE for the country (should match target_locode).")

    class Config:
        # Makes it easier to work with if needed, though direct model_dump() is usually fine
        from_attributes = True

# Path to the markdown file describing GHGI sectors and subsectors
# This will be loaded and used in prompts to give the LLM context
GHGI_SECTORS_PATH = Path(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge_base", 
    "ghgi_sectors.md"
))

EXTRACTOR_PROMPT_PATH = Path(__file__).parent / "prompts" / "extractor_prompt.md"

def load_ghgi_sectors_info() -> str:
    """
    Load GHGI sectors and subsectors information from markdown file.
    Returns placeholder text if file doesn't exist.
    """
    try:
        if GHGI_SECTORS_PATH.exists():
            with open(GHGI_SECTORS_PATH, "r", encoding="utf-8") as f:
                return f.read()
        else:
            logger.warning(f"GHGI sectors file not found: {GHGI_SECTORS_PATH}")
            # Return a more detailed placeholder if file is missing
            return """            
            [This is placeholder text. A 'knowledge_base/ghgi_sectors.md' file should provide official sector definitions.]
            """
    except Exception as e:
        logger.error(f"Error loading GHGI sectors info: {str(e)}")
        return "[Error loading GHGI sectors information]"

def load_extractor_prompt_template() -> str:
    """Loads the extractor prompt template from file."""
    try:
        if EXTRACTOR_PROMPT_PATH.exists():
            return EXTRACTOR_PROMPT_PATH.read_text(encoding="utf-8")
        else:
            logger.error(f"Extractor prompt file not found: {EXTRACTOR_PROMPT_PATH}")
            return "" # Return empty string or a default fallback prompt if critical
    except Exception as e:
        logger.error(f"Error loading extractor prompt file {EXTRACTOR_PROMPT_PATH}: {e}")
        return ""

# This basic function might be less useful now LLM extraction is the primary method
def extract_from_document(document: Dict[str, Any], target_country: Optional[str] = None, target_locode: Optional[str] = None) -> Dict[str, Any]:
    """Create a basic structured record from document metadata (fallback)."""
    extraction_data = ExtractorOutputSchema(
        name=f"Basic Record for {document.get('title', 'Unknown Title')}",
        url=document.get("url", ""),
        method_of_access="web_scrape",
        sector=None,
        subsector=None,
        data_format="html/markdown",
        description=f"Basic extraction from scraped content of {document.get('url', '')}. Title: {document.get('title', 'N/A')}. Requires LLM review.",
        granularity=None,
        country=target_country,
        country_locode=target_locode
    )
    return extraction_data.model_dump(exclude_none=True)

def extract_with_llm(document: Dict[str, Any], target_country: Optional[str], target_locode: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Use OpenRouter LLM to extract structured data from document content.
    Incorporates target country information.
    Attempts to use json_schema mode with ExtractorOutputSchema, falling back to json_object.
    Uses config.STRUCTURED_MODEL.
    
    Args:
        document: Document dictionary with URL and content.
        target_country: Target country name from AgentState.
        target_locode: Target country LOCODE from AgentState.
        
    Returns:
        Structured data as a dictionary, or None if extraction fails badly.
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("OpenAI library not available for LLM extraction.")
        return None # Cannot proceed without OpenAI library
        
    content_to_analyze = document.get("content", "")
    source_url = document.get("url", "")
    if not content_to_analyze:
        logger.warning(f"No content found in document for URL: {source_url}. Skipping LLM extraction.")
        return None

    # Truncate content if it's too long
    max_content_length = 7000  # Adjust based on model context limits
    if len(content_to_analyze) > max_content_length:
        content_to_analyze = content_to_analyze[:max_content_length] + "...[content truncated]..."
    
    ghgi_sectors_info_text = load_ghgi_sectors_info()
    base_prompt_template = load_extractor_prompt_template()

    if not base_prompt_template:
        logger.error("Extractor prompt template failed to load. Aborting LLM extraction.")
        return None

    fields_desc_for_prompt = "\n".join([
        f"- {field_info.alias if field_info.alias else name}: {field_info.description or 'No description'}"
        for name, field_info in ExtractorOutputSchema.model_fields.items()
        if name not in ['country', 'country_locode', 'url'] # These are set post-extraction or are part of input
    ])

    # Format the loaded prompt template
    current_prompt = base_prompt_template.format(
        target_country_or_unknown=target_country or "Unknown",
        url=source_url,
        content=content_to_analyze,
        ghgi_sectors_info=ghgi_sectors_info_text,
        prompt_fields_description=fields_desc_for_prompt
    )
    
    llm_response_content_str = None
    extraction_result_pydantic: Optional[ExtractorOutputSchema] = None

    try:
        client = OpenAI(
            base_url=config.OPENROUTER_BASE_URL,
            api_key=config.OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": config.HTTP_REFERER,
                "X-Title": config.SITE_NAME,
            }
        )
        
        model_to_use_for_extraction = config.STRUCTURED_MODEL
        if not model_to_use_for_extraction:
            logger.error("config.STRUCTURED_MODEL is not set. Cannot perform LLM extraction.")
            return None

        system_prompt_for_llm = (
            f"You are a data extraction specialist focusing on greenhouse gas inventory datasets for {target_country or 'various countries'}. "
            "Your task is to extract information based on the user's prompt and return it ONLY as a valid JSON object that strictly adheres to the provided schema. "
            "Do not include any explanatory text, greetings, or markdown formatting outside the JSON structure itself."
        )
        
        llm_messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt_for_llm},
            {"role": "user", "content": current_prompt}
        ]

        try:
            logger.info(f"Attempting extraction with {model_to_use_for_extraction} for URL {source_url} using json_schema mode.")
            response = client.chat.completions.create(
                model=model_to_use_for_extraction,
                messages=llm_messages,
                response_format={"type": "json_schema", "json_schema": ExtractorOutputSchema.model_json_schema()}, # type: ignore
                temperature=config.DEFAULT_TEMPERATURE,
            )
            llm_response_content_str = response.choices[0].message.content
        except Exception as e_schema:
            logger.warning(f"json_schema mode failed for {model_to_use_for_extraction} on URL {source_url}: {e_schema}. Falling back to json_object mode.")
            try:
                response = client.chat.completions.create(
                    model=model_to_use_for_extraction,
                    messages=llm_messages, 
                    response_format={"type": "json_object"},
                    temperature=config.DEFAULT_TEMPERATURE,
                )
                llm_response_content_str = response.choices[0].message.content
            except Exception as e_object:
                logger.error(f"json_object mode also failed for {model_to_use_for_extraction} on URL {source_url}: {e_object}", exc_info=True)
                return None # Both modes failed

        if not llm_response_content_str:
            logger.warning(f"LLM returned empty content for {source_url} using {model_to_use_for_extraction}.")
            return None

        # Clean and parse the JSON response
        cleaned_llm_response_content = llm_response_content_str.strip()
        if cleaned_llm_response_content.startswith("```json") and cleaned_llm_response_content.endswith("```"):
            cleaned_llm_response_content = cleaned_llm_response_content[7:-3].strip()
        elif cleaned_llm_response_content.startswith("```") and cleaned_llm_response_content.endswith("```"):
            cleaned_llm_response_content = cleaned_llm_response_content[3:-3].strip()
        
        if not cleaned_llm_response_content or cleaned_llm_response_content.isspace():
            logger.warning(f"LLM returned empty content after stripping fences for URL: {source_url}. Returning None.")
            return None

        extraction_result_pydantic = ExtractorOutputSchema.model_validate_json(cleaned_llm_response_content)
        
        # Convert Pydantic model to dict for consistent return type
        extraction_result_dict = extraction_result_pydantic.model_dump(exclude_none=True)
        
        # Add/override fixed/known fields
        extraction_result_dict["url"] = source_url 
        extraction_result_dict["country"] = target_country
        extraction_result_dict["country_locode"] = target_locode
        
        # Pydantic validation is already done by model_validate_json.
        # Additional custom validation could be added here if needed.
        # For example, ensuring extracted country matches target_country more explicitly if not handled by Pydantic.
        if extraction_result_dict.get("country") and target_country and extraction_result_dict["country"] != target_country:
             logger.warning(f"Extracted country '{extraction_result_dict['country']}' does not match target country '{target_country}' for URL {source_url}. Overriding with target.")
             extraction_result_dict["country"] = target_country
        if extraction_result_dict.get("country_locode") and target_locode and extraction_result_dict["country_locode"] != target_locode:
             logger.warning(f"Extracted LOCODE '{extraction_result_dict['country_locode']}' does not match target LOCODE '{target_locode}' for URL {source_url}. Overriding with target.")
             extraction_result_dict["country_locode"] = target_locode
            
        logger.info(f"Successfully extracted and validated structured data via LLM for {source_url} using {model_to_use_for_extraction}.")
        return extraction_result_dict

    except Exception as e: # Catches Pydantic validation errors from model_validate_json or other errors
        logger.error(f"Failed during LLM extraction or validation for {source_url}: {type(e).__name__} - {e}. Response: {str(llm_response_content_str)[:500]}...", exc_info=True)
        return None

def extractor_node(state: AgentState) -> AgentState:
    """
    Processes selected documents from the AgentState, extracts structured data
    using an LLM, and updates the state with the extracted data.
    """
    logger.info(f"EXTRACTOR_NODE: Entered. Current iteration: {state.current_iteration}")
    current_state_dict = asdict(state)
    target_country = current_state_dict.get("target_country")
    target_locode = current_state_dict.get("target_country_locode")
    
    documents_to_process = current_state_dict.get("scraped_data", [])
    current_structured_data = current_state_dict.get("structured_data", [])
    processed_urls = {item.get("url") for item in current_structured_data if item.get("url")}
    
    newly_extracted_count = 0
    for document in documents_to_process:
        doc_url = document.get("url")
        if not doc_url or doc_url in processed_urls:
            continue
        # Skip file/document URLs ( Excel, etc.)
        if needs_advanced_scraping(doc_url):
            logger.info(f"Extractor skipping file/document URL (not extracting): {doc_url}")
            continue

        if "snichile.mma.gob.cl" in doc_url: # TEMPORARY LOGGING
            logger.info(f"DEBUG EXTRACTOR: Content for {doc_url}:\n{document.get('content')[:2000]}\n") # Log first 2000 chars

        logger.info(f"Attempting extraction for document: {doc_url}")
        extraction_result = extract_with_llm(document, target_country, target_locode)
        
        if extraction_result:
            current_structured_data.append(extraction_result)
            processed_urls.add(doc_url)
            newly_extracted_count += 1
            logger.info(f"Successfully extracted and added structured data for: {doc_url}")
        else:
            logger.warning(f"Failed to extract structured data for: {doc_url}")

    logger.info(f"Extractor node finished. Extracted data for {newly_extracted_count} new documents. Current Iteration: {current_state_dict.get('current_iteration')}")
    current_state_dict["structured_data"] = current_structured_data
    current_state_dict["selected_for_extraction"] = [] # Clear after processing

    current_state_dict["decision_log"].append({
        "agent": "Extractor",
        "action": "extraction_complete",
        "documents_processed_in_batch": len(documents_to_process),
        "new_data_items_extracted": newly_extracted_count,
        "total_structured_items": len(current_state_dict["structured_data"])
    })
    
    final_state = AgentState(**current_state_dict)
    logger.info(f"EXTRACTOR_NODE: Exiting. Iteration in final_state: {final_state.current_iteration}")
    return final_state 