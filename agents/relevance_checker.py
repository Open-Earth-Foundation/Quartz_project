import logging
from typing import Dict, Any, Optional
from pathlib import Path
import json  # Added for parsing JSON response
import traceback  # Import traceback

from openai import AsyncOpenAI
from pydantic import BaseModel, Field  # Added Pydantic

import config

logger = logging.getLogger(__name__)

RELEVANCE_CHECK_PROMPT_PATH = (
    Path(__file__).parent / "prompts" / "relevance_check_prompt.md"
)
RELEVANCE_CHECK_FUNDED_PROMPT_PATH = (
    Path(__file__).parent / "prompts" / "relevance_check_funded_projects.md"
)  # NEW


def _strip_code_fences(text: str) -> str:
    """Remove surrounding Markdown code fences (``` or ```json) if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped[3:]
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.lstrip()
        if stripped.endswith("```"):
            stripped = stripped[:-3].rstrip()
    return stripped


class RelevanceCheckError(Exception):
    """Custom exception for relevance check failures."""

    pass


# Define the Pydantic model for structured output
class RelevanceCheckOutput(BaseModel):
    is_relevant: bool = Field(
        description="True if the search result is relevant, False otherwise."
    )
    reason: str = Field(description="A brief explanation for the relevance decision")


def load_relevance_check_prompt_template(search_mode: str = "ghgi_data") -> str:
    """Loads the relevance check prompt template from file based on search mode."""
    # NEW: Select appropriate prompt based on search_mode
    if search_mode == "funded_projects":
        prompt_path = RELEVANCE_CHECK_FUNDED_PROMPT_PATH
        fallback = "URL: {url}\nTitle: {title}\nSnippet: {snippet}\n\nBased on the above for {target_country}, assess its relevance for finding funded climate projects."
    else:
        prompt_path = RELEVANCE_CHECK_PROMPT_PATH
        fallback = "URL: {url}\nTitle: {title}\nSnippet: {snippet}\n\nBased on the above for {target_country}, assess its relevance for finding GHGI datasets or official government emissions statistics."

    try:
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        else:
            logger.error(f"Relevance check prompt file not found: {prompt_path}")
            return fallback
    except Exception as e:
        logger.error(f"Error loading relevance check prompt file {prompt_path}: {e}")
        return fallback


async def check_url_relevance_async(
    search_result: Dict[str, Any],
    target_country: str,
    target_sector: str,
    client: AsyncOpenAI,
    search_mode: str = "ghgi_data",  # NEW: Added search_mode parameter
) -> RelevanceCheckOutput:
    """Check if a URL and its snippet are relevant using an LLM with structured JSON output. Returns a RelevanceCheckOutput object."""
    raw_content = "<not_yet_fetched>"  # Initialize for error logging
    url = search_result.get("url")  # Get URL early for logging in error cases

    try:
        snippet = search_result.get("snippet")
        title = search_result.get("title")

        if not url or not snippet:
            logger.warning(
                f"Missing URL or snippet for relevance check of item: {search_result.get('title', 'N/A')}. Skipping."
            )
            return RelevanceCheckOutput(
                is_relevant=False, reason="Missing URL or snippet"
            )

        if not config.RELEVANCE_CHECK_MODEL:
            logger.warning(
                "RELEVANCE_CHECK_MODEL not configured. Skipping relevance check, assuming relevant by default."
            )
            return RelevanceCheckOutput(
                is_relevant=True,
                reason="RELEVANCE_CHECK_MODEL not configured, assumed relevant",
            )

        # NEW: Use search_mode to select appropriate prompt
        prompt_template = load_relevance_check_prompt_template(search_mode=search_mode)
        current_user_prompt = prompt_template.format(
            target_country=target_country,
            sector=target_sector,
            url=url,
            title=title,
            snippet=snippet,
            lookback_years=config.FUNDED_LOOKBACK_YEARS,  # For funded_projects prompts
        )

        # NEW: Generate search_mode-aware system prompt
        if search_mode == "funded_projects":
            system_prompt = (
                f"You are a climate finance relevance assessment assistant. "
                f"Your task is to determine if the provided web search result is relevant for finding funded climate projects in {target_country}. "
                f"Look for evidence of: funding amounts, funder names, project approval dates, implementation status, and geographic location. "
                f"You must respond with a JSON object that strictly adheres to the following Pydantic schema: {RelevanceCheckOutput.model_json_schema()}. "
                f"Ensure your output is a single, valid JSON object and nothing else."
            )
        else:
            system_prompt = (
                f"You are a data relevance assessment assistant. "
                f"Your task is to determine if the provided web search result is relevant for finding greenhouse gas inventory (GHGI) datasets or official government statistics related to emissions for {target_country}. "
                f"You must respond with a JSON object that strictly adheres to the following Pydantic schema: {RelevanceCheckOutput.model_json_schema()}. "
                f"Ensure your output is a single, valid JSON object and nothing else."
            )

        logger.debug(
            f"Checking relevance for URL: {url} with model: {config.RELEVANCE_CHECK_MODEL} using JSON mode."
        )
        response = await client.chat.completions.create(  # type: ignore
            model=config.RELEVANCE_CHECK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": current_user_prompt},
            ],
            response_format={
                "type": "json_object",
                "schema": RelevanceCheckOutput.model_json_schema(),
            },
            temperature=0.1,
        )

        raw_content = response.choices[0].message.content
        if not raw_content:
            logger.error(f"Relevance check for {url} returned empty content.")
            return RelevanceCheckOutput(
                is_relevant=False,
                reason="LLM returned empty content for relevance check",
            )

        logger.debug(f"Relevance check for {url}: Raw LLM response: '{raw_content}'")
        cleaned_content = _strip_code_fences(raw_content)
        parsed_output = RelevanceCheckOutput.model_validate_json(cleaned_content)

        logger.info(
            f"Relevance check for {url}: Relevant: {parsed_output.is_relevant}, Reason: '{parsed_output.reason}'"
        )
        return parsed_output

    except KeyError as e_key:
        logger.error(
            f"KeyError during relevance check for URL {url}. Key: {e_key}. Traceback: {traceback.format_exc()}"
        )
        # Re-raise specific errors if researcher.py is expected to handle them for retry or specific flow control.
        # For now, returning a "False" RelevanceCheckOutput to ensure function signature is met.
        # Consider if specific exceptions should still be raised.
        return RelevanceCheckOutput(
            is_relevant=False, reason=f"KeyError during processing: {e_key}"
        )
    except json.JSONDecodeError as e_json:
        logger.error(
            f"JSONDecodeError parsing relevance check response for URL {url}. Raw content: '{raw_content}'. Error: {e_json}",
            exc_info=True,
        )
        return RelevanceCheckOutput(
            is_relevant=False, reason=f"JSONDecodeError: {e_json}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error during relevance check for URL {url} with model {config.RELEVANCE_CHECK_MODEL}: {e}",
            exc_info=True,
        )
        return RelevanceCheckOutput(is_relevant=False, reason=f"Unexpected error: {e}")
