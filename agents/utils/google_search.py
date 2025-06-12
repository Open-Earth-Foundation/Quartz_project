import asyncio
import logging
from typing import List, Dict, Any, Optional
import functools
import concurrent.futures

import googleapiclient.discovery

import config
from agent_state import AgentState # Assuming AgentState is in agents package root or accessible
# Assuming retry_with_backoff is now in agents.utils (re-exported by __init__.py)
from agents.utils import retry_with_backoff 

logger = logging.getLogger(__name__)

@retry_with_backoff() # Apply decorator to the async operation that executes sync code
async def google_search_async(query: str, n: int = 10, cse_id: str | None = None, api_key: str | None = None, state: Optional[AgentState] = None) -> List[Dict[str, Any]]: 
    """
    Perform an asynchronous search using Google Programmable Search Engine (CSE).
    The actual search is synchronous and run in a thread pool.
    The retry logic is applied to the async wrapper around the threaded execution.

    Args:
        query: The search query string
        n: Maximum number of results to return
        cse_id: Custom Search Engine ID (from config if not provided)
        api_key: Google API key (from config if not provided)
        state: Optional AgentState for updating metrics.
    Returns:
        List of search result items (dicts with url, title, snippet), or empty list on failure.
    """
    if cse_id is None: cse_id = getattr(config, "GOOGLE_CSE_ID", None)
    if api_key is None: api_key = getattr(config, "GOOGLE_API_KEY", None)
    
    if not cse_id or not api_key:
        logger.error("Google CSE ID or API key not set in config.")
        if state and hasattr(state, 'api_calls_failed'): state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return []
    
    final_cse_id: str = cse_id
    final_api_key: str = api_key

    def _sync_google_search(p_query: str, p_n: int, p_cse_id: str, p_api_key: str):
        # This remains a synchronous function. It should raise exceptions on failure.
        try:
            service = googleapiclient.discovery.build("customsearch", "v1", developerKey=p_api_key, cache_discovery=False)
            res = service.cse().list(q=p_query, cx=p_cse_id, num=p_n).execute()
            return res
        except Exception as e:
            logger.error(f"Error in _sync_google_search for query '{p_query}': {e}", exc_info=False)
            raise

    async def _execute_search_in_executor(current_state: Optional[AgentState] = None):
        loop = asyncio.get_event_loop()
        raw_results = await loop.run_in_executor(
            None, 
            functools.partial(_sync_google_search, query, n, final_cse_id, final_api_key)
        )
        
        parsed_results = []
        if raw_results and "items" in raw_results:
            for item in raw_results["items"]:
                parsed_results.append({
                    "url": item.get("link"),
                    "title": item.get("title"),
                    "snippet": item.get("snippet")
                })
        if current_state and hasattr(current_state, 'api_calls_succeeded'): 
            current_state.api_calls_succeeded = getattr(current_state, 'api_calls_succeeded', 0) + 1
        return parsed_results[:n]

    try:
        return await _execute_search_in_executor(current_state=state) 
    except Exception as e: 
        logger.error(f"Google search for query '{query}' ultimately failed after retries: {e}")
        return []
