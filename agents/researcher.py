"""
Researcher Agent - Responsible for iterative research and retrieval.

This agent:
1. Performs broad searches based on the query
2. Prioritizes promising sources using country context
3. Adapts search strategy if initial results are poor
4. Extracts and collects relevant URLs and document content
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import re
from urllib.parse import urlparse
from datetime import datetime, timezone
from dataclasses import asdict
from functools import partial
import os  # Import os for path operations
import json  # Import json for saving
import requests  # Import requests to catch HTTPError
import copy  # Add copy import

# Import project modules first, then third-party for clarity
import config
from agent_state import AgentState
from agents.utils import (
    google_search_async,  # Import the new Google search function
    needs_advanced_scraping,
    sanitize_filename,
    load_and_chunk_html_content,
    scrape_urls_async,  # IMPORTED from agents.utils (via __init__.py)
)
from agents.utils.file_saver import save_scrape_to_file  # CORRECTED IMPORT
from agents.schemas import SearchQuery as SchemaSearchQuery
from agents.relevance_checker import (
    check_url_relevance_async,
    RelevanceCheckError,
    RelevanceCheckOutput,
)

# Third-party imports
# from firecrawl import FirecrawlApp # type: ignore # REMOVE
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)
from openai import OpenAI, AsyncOpenAI

# Set up logging
logger = logging.getLogger(__name__)


async def collect_search_results(
    query: str,
    country_name: Optional[str] = None,
    country_locode: Optional[
        str
    ] = None,  # Keep for potential future use or consistency
    max_results: Optional[int] = None,
    # use_google: bool = True, # REMOVE - Always use Google
    google_quota: Optional[int] = None,
    save_raw_results: bool = True,
    save_dir: str = "logs/search_api_outputs",
    state: Optional[AgentState] = None,  # Added for search_mode detection
) -> List[Dict[str, Any]]:
    """
    Collect search results for a query using Google Search.
    Saves raw results to a JSON file if requested.
    Args:
        query: The search query
        country_name: The target country name for query expansion
        country_locode: The target country code for domain prioritization (currently unused but kept for consistency)
        max_results: Maximum number of results to return
        google_quota: Remaining Google queries allowed
        save_raw_results: Whether to save the raw search engine results.
        save_dir: Directory to save the raw results.
        state: AgentState for detecting search_mode (ghgi_data or funded_projects)
    Returns:
        List of search result items (dictionaries)
    """
    if max_results is None:
        max_results = config.MAX_RESULTS_PER_QUERY
    if google_quota is None:
        google_quota = config.MAX_GOOGLE_QUERIES_PER_RUN

    logger.info(f"Performing Google search for: {query}")
    raw_results_list: List[Dict[str, Any]] = []
    search_engine_used = "google"  # Always Google

    # MODIFIED: Dual-mode query construction (Option A & B Implementation)
    # Exclude certain filetypes from search results
    # PDFs are included in search results but NOT scraped (links saved, content ignored)
    exclusions = [
        "-filetype:xlsx",
        "-filetype:xls",
        "-filetype:docx",
        "-filetype:doc",
        "-filetype:pptx",
        "-filetype:ppt",
        "-filetype:zip",
    ]
    exclusion_string = " ".join(exclusions)

    # Determine search mode and construct query appropriately
    search_mode = getattr(state, "search_mode", "ghgi_data") if state else "ghgi_data"
    if state:
        logger.info(
            f"[DEBUG collect_search_results] state.search_mode={getattr(state, 'search_mode', 'NOT_SET')}, search_mode var={search_mode}"
        )

    if search_mode == "funded_projects":
        # For funded projects: add funding keywords, allow PDFs
        lookback_hint = f"funded OR funding OR grant OR approved OR implementation OR budget last {config.FUNDED_LOOKBACK_YEARS} years"
        current_query = f"{query} {lookback_hint} {exclusion_string}"
        logger.info(
            f"[FUNDED_PROJECTS MODE] Query modified with funding keywords. New query: '{current_query}'"
        )
    else:
        # For GHGI data: no funding keywords, allow PDFs (activity data is often in PDFs)
        current_query = f"{query} {exclusion_string}"
        logger.info(
            f"[GHGI_DATA MODE] Query constructed without funding keywords. New query: '{current_query}'"
        )

    try:
        if google_quota > 0:  # Check quota before calling
            raw_results_list = await google_search_async(current_query, max_results)
            google_quota -= 1
            logger.info(
                f"Google search successful for query '{current_query}'. Results: {len(raw_results_list)}. Remaining quota: {google_quota}"
            )
        else:
            logger.warning(
                f"Google search quota depleted. Cannot perform search for query: {current_query}"
            )
            raw_results_list = []
    except Exception as search_error:
        logger.error(
            f"Google search failed for query '{current_query}': {search_error!r}",
            exc_info=True,
        )
        raw_results_list = []

    if save_raw_results and raw_results_list:
        try:
            os.makedirs(save_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Use the original query for sanitizing filename, not the modified one with -filetype:pdf
            query_sanitized = re.sub(r"[^\\w\\-_]", "_", query)[:50]
            country_sanitized = re.sub(r"[^\\w\\-_]", "_", country_name or "NoCountry")
            filename = f"{search_engine_used}_results_{country_sanitized}_{query_sanitized}_{timestamp}.json"
            filepath = os.path.join(save_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    copy.deepcopy(raw_results_list), f, indent=4, ensure_ascii=False
                )
            logger.info(
                f"Saved raw {search_engine_used} search results for query '{query}' to: {filepath}"
            )
        except Exception as e_save:
            logger.error(f"Failed to save raw search results: {e_save}")
    elif save_raw_results:
        logger.info(
            f"No results obtained from {search_engine_used} for query '{query}', skipping save."
        )

    # Directly use the raw results, limited by max_results
    final_results = raw_results_list[:max_results]
    logger.info(
        f"Collected {len(final_results)} total results for query '{query}' (heuristic prioritization removed)."
    )
    # --- END REMOVED Prioritization Logic --- #
    return final_results


async def researcher_node(state: AgentState) -> AgentState:
    """Researcher node: executes search plan, collects, and scrapes data."""
    logger.info(
        f"DEBUG_RESEARCHER: Received state in researcher. ID: {id(state)}, Iteration: {state.current_iteration}"
    )
    logger.info("Researcher node activated.")

    client = AsyncOpenAI(  # MODIFIED: Changed to AsyncOpenAI
        base_url=config.OPENROUTER_BASE_URL,
        api_key=config.OPENROUTER_API_KEY,
        default_headers={
            "HTTP-Referer": config.HTTP_REFERER,
            "X-Title": config.SITE_NAME,
        },
    )

    start_time_researcher = datetime.now()
    research_summary = {
        "target_country": state.target_country,
        "queries_processed_this_cycle": [],
        "urls_collected_this_cycle": 0,
        "relevant_urls_for_scraping_this_cycle": 0,
        "scraped_data_items_added_this_cycle": 0,
        "errors_this_cycle": [],
    }

    current_search_plan = [
        item for item in state.search_plan if item.get("status") == "pending"
    ]
    current_search_plan.sort(key=lambda x: x.get("rank", float("inf")))  # Sort by rank

    all_collected_search_results: List[Dict[str, Any]] = []
    processed_query_count = 0

    # --- Process regular search plan --- #
    for plan_item_dict in current_search_plan:
        if processed_query_count >= config.MAX_QUERIES_PER_RESEARCH_CYCLE:
            logger.info(
                f"Reached max queries per research cycle ({config.MAX_QUERIES_PER_RESEARCH_CYCLE}). Deferring remaining queries."
            )
            break

        try:
            plan_item = SchemaSearchQuery(
                **plan_item_dict
            )  # Validate/convert to Pydantic model
        except Exception as e:  # Catch Pydantic validation error or others
            logger.error(
                f"Skipping invalid search plan item: {plan_item_dict}. Error: {e}"
            )
            research_summary["errors_this_cycle"].append(
                f"Invalid plan item {plan_item_dict}: {e}"
            )
            continue

        logger.info(
            f"Processing search query: '{plan_item.query}' (Priority: {plan_item.priority}, Lang: {plan_item.language})"
        )
        search_results_for_query = await collect_search_results(
            query=plan_item.query,
            country_name=state.target_country or "UnknownCountry",
            max_results=config.MAX_RESULTS_PER_QUERY,
            # use_google=True, # REMOVED - no longer an option
            save_raw_results=True,
            save_dir=SEARCH_API_OUTPUT_DIR,
            state=state,  # Pass state for search_mode detection
        )
        all_collected_search_results.extend(search_results_for_query)
        research_summary["queries_processed_this_cycle"].append(plan_item.query)
        research_summary["urls_collected_this_cycle"] += len(search_results_for_query)

        # Update status of the processed plan item
        for sp_item in state.search_plan:
            if sp_item.get("query") == plan_item.query:
                sp_item["status"] = "searched"
                break
        processed_query_count += 1

    # Consolidate URLs and remove duplicates before relevance check or scraping
    unique_urls_to_consider = list(
        set(res.get("url") for res in all_collected_search_results if res.get("url"))
    )
    # Filter out None URLs explicitly after creating the set to satisfy type checker for relevance_check_tasks
    unique_urls_to_consider_filtered: List[str] = [
        url for url in unique_urls_to_consider if url is not None
    ]

    # MOVED search_results_by_url definition EARLIER
    search_results_by_url = {
        res.get("url"): res for res in all_collected_search_results if res.get("url")
    }

    # --- ADDED: Incorporate deep dive actions if present --- #
    def process_deep_dive_action(action: Dict[str, Any]) -> bool:
        action_type = action.get("action_type")
        target_url = action.get("target")

        if action_type == "scrape" and target_url:
            logger.info(
                f"Researcher received a direct scrape request from deep_diver for URL: {target_url}"
            )
            if target_url not in unique_urls_to_consider_filtered:
                unique_urls_to_consider_filtered.append(target_url)
                logger.info(
                    f"Added deep_dive_target_url {target_url} to unique_urls_to_consider_filtered."
                )
                if target_url not in search_results_by_url:
                    search_results_by_url[target_url] = {
                        "url": target_url,
                        "title": "Deep Dive Scrape Target",
                        "snippet": "Manually added for deep dive scrape action.",
                        "source": "deep_dive_scrape",
                    }
            else:
                logger.info(
                    f"Deep_dive_target_url {target_url} is already in unique_urls_to_consider_filtered."
                )
            return True

        if action_type == "crawl" and target_url:
            logger.info(
                f"Researcher received a crawl request from deep_diver for URL: {target_url}"
            )

            max_pages = action.get("max_pages", 10)
            exclude_patterns = action.get("exclude_patterns", [])

            from agents.utils.scraping import crawl_website

            try:
                crawl_results = crawl_website(
                    base_url=target_url,
                    max_pages=max_pages,
                    exclude_patterns=exclude_patterns,
                    state=state,
                )

                logger.info(
                    f"Crawl completed for {target_url}. Found {len(crawl_results)} pages."
                )

                for crawl_item in crawl_results:
                    if crawl_item.get("success") and crawl_item.get("url"):
                        crawled_url = crawl_item["url"]
                        if crawled_url not in unique_urls_to_consider_filtered:
                            unique_urls_to_consider_filtered.append(crawled_url)
                            if crawled_url not in search_results_by_url:
                                search_results_by_url[crawled_url] = {
                                    "url": crawled_url,
                                    "title": crawl_item.get("title", "Crawled Page"),
                                    "snippet": crawl_item.get(
                                        "description", "Found via website crawl"
                                    ),
                                    "source": "deep_dive_crawl",
                                }

                logger.info(
                    f"Added {len([r for r in crawl_results if r.get('success')])} crawled URLs to processing list."
                )

            except Exception as e:
                logger.error(
                    f"Error during website crawl for {target_url}: {e}",
                    exc_info=True,
                )
            return True

        if action_type == "terminate_deep_dive":
            logger.info(
                "Deep dive action is terminate_deep_dive. No additional URLs added."
            )
            return False

        logger.warning(f"Unknown or incomplete deep dive action: {action}")
        return False

    deep_dive_actions = state.metadata.get("deep_dive_actions")
    if isinstance(deep_dive_actions, list) and deep_dive_actions:
        logger.info(f"Researcher received {len(deep_dive_actions)} deep dive actions.")
        for action in deep_dive_actions:
            if isinstance(action, dict):
                process_deep_dive_action(action)
            else:
                logger.warning(f"Skipping invalid deep dive action entry: {action}")
        state.metadata.pop("deep_dive_actions", None)
        state.metadata.pop("deep_dive_action", None)
        logger.info(
            "Cleared deep_dive_actions and deep_dive_action from state metadata after processing."
        )
    else:
        deep_dive_action = state.metadata.get("deep_dive_action", {})
        if isinstance(deep_dive_action, dict) and deep_dive_action:
            if process_deep_dive_action(deep_dive_action):
                state.metadata.pop("deep_dive_action", None)
                logger.info(
                    "Cleared deep_dive_action from state metadata after processing deep dive action."
                )

    relevant_urls_to_scrape: List[str] = []
    if config.ENABLE_PRE_SCRAPE_RELEVANCE_CHECK and unique_urls_to_consider_filtered:
        logger.info(
            f"Performing pre-scrape relevance check for {len(unique_urls_to_consider_filtered)} unique URLs."
        )
        relevance_check_tasks = [
            check_url_relevance_async(
                search_results_by_url.get(
                    url, {"url": url, "title": "", "snippet": ""}
                ),
                state.target_country or "UnknownCountry",
                state.target_sector or "Any",
                client,
                search_mode=state.search_mode,  # NEW: Pass search_mode to relevance checker
                primary_languages=state.metadata.get(
                    "primary_languages", []
                ),  # NEW: Pass primary languages
            )
            for url in unique_urls_to_consider_filtered  # Use the filtered list
        ]
        relevance_results = await asyncio.gather(
            *relevance_check_tasks, return_exceptions=True
        )

        for i, url in enumerate(
            unique_urls_to_consider_filtered
        ):  # Use the filtered list
            result_item = relevance_results[i]
            if isinstance(result_item, Exception):
                # MODIFIED LOGGING for better diagnostics
                logger.error(
                    f"Relevance check failed for {url}. Error: {result_item!r}, Type: {type(result_item)}. Skipping."
                )
            elif isinstance(
                result_item, RelevanceCheckOutput
            ):  # Check if it's the Pydantic model
                if result_item.is_relevant:
                    relevant_urls_to_scrape.append(url)
                    logger.info(
                        f"URL marked as RELEVANT for scraping: {url}. Reason: '{result_item.reason}'"
                    )
                else:
                    logger.info(
                        f"URL marked as NOT RELEVANT for scraping: {url}. Reason: '{result_item.reason}' (Raw bool: {result_item.is_relevant})"
                    )
            else:  # Should not happen if relevance_checker.py is correct, but good to have a fallback
                logger.warning(
                    f"URL relevance check for {url} returned an unexpected type: {type(result_item)}. Value: {result_item!r}. Assuming NOT RELEVANT."
                )
    else:
        logger.info(
            "Pre-scrape relevance check is disabled or no URLs to check. Proceeding with all unique URLs for scraping."
        )
        relevant_urls_to_scrape = (
            unique_urls_to_consider_filtered  # Use the filtered list here as well
        )

    research_summary["relevant_urls_for_scraping_this_cycle"] = len(
        relevant_urls_to_scrape
    )
    logger.info(
        f"Identified {len(relevant_urls_to_scrape)} relevant URLs for scraping."
    )

    # --- Scraping Relevant URLs ---
    scraped_data_results: List[Dict[str, Any]] = (
        []
    )  # Ensure variable is named scraped_data_results
    if relevant_urls_to_scrape:
        logger.info(
            f"Attempting to scrape {len(relevant_urls_to_scrape)} relevant URLs."
        )

        scraped_data_results = await scrape_urls_async(
            urls=relevant_urls_to_scrape, state=state  # Pass the whole state object
        )
        logger.info(
            f"Scraping complete via scrape_urls_async. Processing {len(scraped_data_results)} results."
        )

        # After scraping, save the HTML content to the new directory structure
        successful_html_saves = 0
        if scraped_data_results:  # Check if there are any results to process
            # MODIFIED: Access state attributes directly
            current_sector = state.target_sector or "unknown_sector"

            # Use state.start_time for run_id, and sanitize it
            raw_run_id = state.start_time

            sanitized_run_id_from_time = (
                raw_run_id.replace(":", "-").replace("T", "_").split(".")[0]
            )
            current_run_id = sanitized_run_id_from_time

            if not current_run_id:  # Fallback, though start_time should always exist
                current_run_id = datetime.now(timezone.utc).strftime(
                    "%Y%m%d_%H%M%S_fallback"
                )
                logger.warning(
                    f"run_id derived from start_time was empty, generated fallback: {current_run_id}"
                )

            country_name_for_path = state.target_country or "UnknownCountry"

            for item in scraped_data_results:
                if item.get("success") and item.get("html_content") and item.get("url"):
                    html_content_to_save = item["html_content"]
                    original_url = item["url"]

                    filename_prefix = (
                        original_url.replace("https://", "")
                        .replace("http://", "")
                        .replace("/", "_")
                    )
                    max_prefix_len = 100  # Max length for the prefix part before .html
                    sanitized_prefix = sanitize_filename(
                        filename_prefix[:max_prefix_len]
                    )
                    scraped_filename = f"{sanitized_prefix}.html"

                    try:
                        saved_path = save_scrape_to_file(
                            data=html_content_to_save,
                            country_name=country_name_for_path,
                            filename=scraped_filename,
                            sector=current_sector,
                            run_id=current_run_id,
                        )
                        if saved_path:
                            logger.info(
                                f"Saved HTML content for {original_url} to {saved_path}"
                            )
                            # Optionally, add saved_filepath to the item in scraped_data_results
                            if isinstance(
                                item, dict
                            ):  # Ensure item is a dict before adding key
                                item["saved_html_filepath"] = saved_path
                            successful_html_saves += 1
                        else:
                            logger.error(
                                f"Failed to save HTML content for {original_url} (save_scrape_to_file returned None)."
                            )
                            if isinstance(item, dict):
                                item["saved_html_filepath"] = (
                                    None  # Indicate save failure
                                )
                            research_summary["errors_this_cycle"].append(
                                f"Save HTML error for {original_url}: save_scrape_to_file returned None"
                            )
                    except Exception as e_save_html:
                        logger.error(
                            f"Exception saving HTML for {original_url} in dir {current_sector}_{current_run_id}: {e_save_html}",
                            exc_info=True,
                        )
                        if isinstance(item, dict):
                            item["saved_html_filepath"] = (
                                None  # Indicate save failure due to exception
                            )
                        research_summary["errors_this_cycle"].append(
                            f"Exception saving HTML for {original_url}: {e_save_html}"
                        )

            logger.info(
                f"Attempted to save HTML for {len(scraped_data_results)} scraped items, successfully saved {successful_html_saves} HTML files."
            )
        else:
            logger.info("No results from scrape_urls_async to save HTML from.")

        # This counts items with markdown content from scraping, not necessarily successfully saved HTML files.
        # The number of *successfully scraped items* (which might have markdown) is len([d for d in scraped_data_results if d.get('success')])
        successfully_scraped_items_count = len(
            [d for d in scraped_data_results if d.get("success") and d.get("content")]
        )
        research_summary["scraped_data_items_added_this_cycle"] = (
            successfully_scraped_items_count
        )
        logger.info(
            f"Successfully processed {successfully_scraped_items_count} items with markdown from scraping. {successful_html_saves} HTML files saved."
        )
    else:
        logger.info("No relevant URLs to scrape in this cycle.")

    # ... (rest of the node, updating state.scraped_data, decision_log, saving summary)
    updated_scraped_data = list(state.scraped_data)  # Make a mutable copy
    # Add new data, avoiding duplicates based on URL (or a more robust ID if available)
    existing_scraped_urls = {
        doc.get("url") for doc in updated_scraped_data if doc.get("url")
    }
    for new_doc in scraped_data_results:  # Use only successful scrapes
        if new_doc.get("url") not in existing_scraped_urls:
            updated_scraped_data.append(new_doc)
            existing_scraped_urls.add(new_doc.get("url"))

    # Save research summary
    timestamp = start_time_researcher.strftime("%Y%m%d_%H%M%S")
    country_name_sanitized = (
        re.sub(r"[^\\w_.)( -]", "", state.target_country or "UnknownCountry")
        .strip()
        .replace(" ", "_")
    )
    summary_filename = os.path.join(
        RESEARCHER_OUTPUT_DIR,
        f"researcher_cycle_output_{country_name_sanitized}_{timestamp}.json",
    )
    try:
        os.makedirs(RESEARCHER_OUTPUT_DIR, exist_ok=True)
        with open(summary_filename, "w", encoding="utf-8") as f:
            json.dump(research_summary, f, indent=2, ensure_ascii=False)
        logger.info(f"Researcher cycle summary saved to: {summary_filename}")
    except Exception as e:
        logger.error(f"Failed to save researcher cycle summary: {e}")

    state.decision_log.append(
        {
            "agent": "Researcher",
            "action": "research_iteration_completed",
            "queries_processed": research_summary["queries_processed_this_cycle"],
            "urls_collected": research_summary["urls_collected_this_cycle"],
            "relevant_urls_for_scraping": research_summary[
                "relevant_urls_for_scraping_this_cycle"
            ],
            "new_data_items": research_summary["scraped_data_items_added_this_cycle"],
        }
    )

    return AgentState(
        prompt=state.prompt,
        search_plan=state.search_plan,  # Pass the updated plan (with statuses)
        urls=state.urls,  # Consider if this should be updated or if scraped_data is enough
        scraped_data=updated_scraped_data,
        structured_data=state.structured_data,
        decision_log=state.decision_log,
        confidence_scores=state.confidence_scores,
        iteration_count=state.iteration_count,
        start_time=state.start_time,
        metadata=state.metadata,
        target_country=state.target_country,
        target_country_locode=state.target_country_locode,
        searches_conducted_count=state.searches_conducted_count + processed_query_count,
        current_iteration=state.current_iteration,  # Researcher node does not increment main iteration count
        target_sector=state.target_sector,
        target_city=state.target_city,
        target_region=state.target_region,
        research_mode=state.research_mode,
        search_mode=state.search_mode,  # CRITICAL: Pass through search_mode
        consecutive_deep_dive_count=state.consecutive_deep_dive_count,
        selected_for_extraction=state.selected_for_extraction,
        current_deep_dive_actions_count=state.current_deep_dive_actions_count,
        partial_project=state.partial_project,
    )


# ... (rest of researcher.py, e.g. __main__ block if present)

# Define output directories
SEARCH_API_OUTPUT_DIR = os.path.join(os.getcwd(), "logs", "search_api_outputs")
RESEARCHER_OUTPUT_DIR = os.path.join(os.getcwd(), "logs", "researcher_outputs")
