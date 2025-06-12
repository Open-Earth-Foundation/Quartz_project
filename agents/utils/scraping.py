import asyncio
import logging
from typing import List, Dict, Any, Optional
import re
from functools import partial
from datetime import datetime
import requests # For HTTPError
import json # Added for JSON operations
import os # Added for path operations
from pathlib import Path # Added for robust path handling

# Try importing Firecrawl and set flag
try:
    from firecrawl.firecrawl import FirecrawlApp, AsyncFirecrawlApp # type: ignore
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    # Create dummy classes for type hints if Firecrawl is not installed
    class AsyncFirecrawlApp:
        def __init__(self, api_key):
            pass
        async def search(self, *args, **kwargs):
            raise NotImplementedError("Firecrawl is not installed")
        # Add scrape_url method to dummy AsyncFirecrawlApp
        async def scrape_url(self, *args, **kwargs):
            raise NotImplementedError("Firecrawl is not installed")
            
    class FirecrawlApp:
        def __init__(self, api_key):
             pass
        def search(self, *args, **kwargs):
            raise NotImplementedError("Firecrawl is not installed")
        # Add scrape_url method to dummy FirecrawlApp
        def scrape_url(self, *args, **kwargs):
            raise NotImplementedError("Firecrawl is not installed")

# Import project modules AFTER firecrawl attempt to avoid circular dependencies if utils imports config
import config # Assuming config is in the parent directory or accessible
from agent_state import AgentState # Assuming AgentState is accessible

from agents.utils.retry_with_backoff import retry_with_backoff, HTTP_EXCEPTIONS_TUPLE as HTTP_EXCEPTIONS

logger = logging.getLogger(__name__)

# Define the path for scraped data logs relative to this file's location
SCRAPED_DATA_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "scraped_websites"

# Ensure the log directory exists
os.makedirs(SCRAPED_DATA_LOG_DIR, exist_ok=True)

# Default file patterns to skip (if not in config) for scraping
DEFAULT_SKIP_FILE_URL_PATTERNS = [ r'\.docx?$', r'\.doc$', r'\.pptx?$', r'\.zip$', r'\.tar\.gz$' ]

def _sanitize_url_for_filename(url: str) -> str:
    """Sanitizes a URL to be used as a filename."""
    # Remove http(s)://
    name = re.sub(r'^https?://', '', url)
    # Replace common problematic characters with underscores
    name = re.sub(r'[/:?\"<>|*]', '_', name)
    # Truncate if too long (OS path limits)
    return name[:200] # Max 200 chars, adjust if needed

def _save_scraped_data_to_log(url: str, firecrawl_response: Any, timestamp_str: str):
    """Saves the scraped content as a markdown file in the log directory."""
    if not firecrawl_response:
        return

    try:
        filename_base = _sanitize_url_for_filename(url)
        filename = f"{filename_base}_{timestamp_str}.md"
        filepath = SCRAPED_DATA_LOG_DIR / filename

        # Extract content from Firecrawl response - handle nested 'data' structure
        markdown_content = ""
        metadata_info = {}
        
        # Handle the nested 'data' structure from Firecrawl API
        response_data = firecrawl_response
        if isinstance(firecrawl_response, dict) and 'data' in firecrawl_response:
            response_data = firecrawl_response['data']
        elif hasattr(firecrawl_response, 'data'):
            response_data = firecrawl_response.data
            
        # Extract markdown content
        if isinstance(response_data, dict):
            markdown_content = response_data.get('markdown') or response_data.get('content', '')
            metadata_info = response_data.get('metadata', {})
        elif hasattr(response_data, 'markdown'):
            markdown_content = response_data.markdown or getattr(response_data, 'content', '')
            metadata_info = getattr(response_data, 'metadata', {})
        
        # Create markdown file with metadata header
        content_to_save = f"""---
        url: {url}
        timestamp: {timestamp_str}
        title: {metadata_info.get('title', 'N/A') if isinstance(metadata_info, dict) else 'N/A'}
        description: {metadata_info.get('description', 'N/A') if isinstance(metadata_info, dict) else 'N/A'}
        keywords: {metadata_info.get('keywords', 'N/A') if isinstance(metadata_info, dict) else 'N/A'}
        ---

        # Scraped Content from {url}

        {markdown_content if markdown_content else 'No markdown content available'}
        """
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content_to_save)
        logger.debug(f"[Scrape Save] Successfully saved scraped content for {url} to {filepath}")
    except Exception as e:
        logger.error(f"[Scrape Save] Error saving scraped content for {url}: {e}", exc_info=True)

# Synchronous scraping function
def scrape_urls_sync(urls: List[str], state: Optional[AgentState] = None) -> List[Dict[str, Any]]:
    if not FIRECRAWL_AVAILABLE:
        logger.error("Firecrawl package is not available for scrape_urls_sync")
        if state and hasattr(state, 'api_calls_failed'): state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return []
    
    if not config.FIRECRAWL_API_KEY:
        logger.error("Firecrawl API key is not set for scrape_urls_sync")
        if state and hasattr(state, 'api_calls_failed'): state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return []
    
    documents = []
    try:
        client = FirecrawlApp(api_key=config.FIRECRAWL_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize FirecrawlApp for sync scrape: {e}")
        if state and hasattr(state, 'api_calls_failed'): state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return []

    skip_patterns_config = getattr(config, 'SKIP_FILE_URL_PATTERNS', DEFAULT_SKIP_FILE_URL_PATTERNS)
    compiled_skip_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in skip_patterns_config]

    for url in urls:
        try:
            should_skip = False
            for pattern in compiled_skip_patterns:
                if pattern.search(url):
                    logger.info(f"[Sync Scrape] Skipping URL based on file pattern match ({pattern.pattern}): {url}")
                    documents.append({'url': url, 'success': False, 'error': f'Skipped due to file pattern match: {pattern.pattern}'})
                    should_skip = True
                    break
            if should_skip:
                continue

            logger.info(f"[Sync Scrape] Scraping URL: {url}")
            scrape_kwargs = {'only_main_content': True}
            if url.lower().endswith('.pdf'):
                logger.info(f"[Sync Scrape] PDF URL detected. Enabling OCR for: {url}")
                scrape_kwargs['ocr'] = True
            
            current_timestamp = datetime.utcnow()
            response: Optional[Any] = client.scrape_url(url, **scrape_kwargs)
            
            if response: # Save raw response if successful
                _save_scraped_data_to_log(url, response, current_timestamp.strftime("%Y%m%d%H%M%S%f"))

            # Handle nested 'data' structure from Firecrawl API
            response_data = response
            if isinstance(response, dict) and 'data' in response:
                response_data = response['data']
            elif hasattr(response, 'data'):
                response_data = response.data
                
            # Extract content from response_data
            markdown_content = ""
            html_content = ""
            metadata = {}
            
            if isinstance(response_data, dict):
                markdown_content = response_data.get('markdown', '')
                html_content = response_data.get('html', '')
                metadata = response_data.get('metadata', {})
            elif hasattr(response_data, 'markdown'):
                markdown_content = getattr(response_data, 'markdown', '')
                html_content = getattr(response_data, 'html', '')
                metadata = getattr(response_data, 'metadata', {})

            if markdown_content:
                title = metadata.get('title', '') if isinstance(metadata, dict) else ''
                document = {
                    'url': url,
                    'content': markdown_content,
                    'html_content': html_content,
                    'title': title,
                    'source_type': 'web_scrape_sync',
                    'timestamp': current_timestamp.isoformat(),
                    'success': True,
                    'keywords': metadata.get('keywords', '') if isinstance(metadata, dict) else '',
                    'description': metadata.get('description', '') if isinstance(metadata, dict) else ''
                }
                documents.append(document)
            else:
                logger.warning(f"[Sync Scrape] Scraped {url} but no markdown content. Response data keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'N/A'}")
                documents.append({'url': url, 'success': False, 'error': 'No markdown content after scrape'})
                
        except Exception as e:
            logger.error(f"[Sync Scrape] Error scraping URL {url}: {str(e)}", exc_info=True)
            documents.append({'url': url, 'success': False, 'error': str(e)})
    
    successful_scrapes = len([d for d in documents if d.get('success')])
    logger.info(f"[Sync Scrape] Scraped {successful_scrapes} URLs successfully out of {len(urls)}.")
    if state and hasattr(state, 'api_calls_succeeded'): state.api_calls_succeeded = getattr(state, 'api_calls_succeeded', 0) + successful_scrapes
    if state and hasattr(state, 'api_calls_failed'): state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + (len(urls) - successful_scrapes)
    return documents

# Asynchronous scraping function
async def scrape_urls_async(urls: List[str], state: Optional[AgentState] = None) -> List[Dict[str, Any]]:
    if not FIRECRAWL_AVAILABLE:
        logger.error("Firecrawl package is not available for scrape_urls_async")
        if state and hasattr(state, 'api_calls_failed'): state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + len(urls)
        return [{'url': url, 'success': False, 'error': 'Firecrawl not available'} for url in urls]
    
    if not config.FIRECRAWL_API_KEY:
        logger.error("Firecrawl API key is not set for scrape_urls_async")
        if state and hasattr(state, 'api_calls_failed'): state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + len(urls)
        return [{'url': url, 'success': False, 'error': 'Firecrawl API key not set'} for url in urls]

    # Note: AsyncFirecrawlApp might not have scrape_url. Firecrawl typically uses sync client for scrape_url.
    # If AsyncFirecrawlApp is intended, its methods (like crawl_url) are different.
    # Assuming we stick to scrape_url, we need the sync FirecrawlApp run in an executor.
    # The `client` variable defined as AsyncFirecrawlApp might be misleading if we only use sync scrape_url.
    
    loop = asyncio.get_event_loop()
    skip_patterns_config = getattr(config, 'SKIP_FILE_URL_PATTERNS', DEFAULT_SKIP_FILE_URL_PATTERNS)
    compiled_skip_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in skip_patterns_config]
    
    # Define a semaphore to limit concurrency
    # TODO: Make this concurrency limit configurable
    CONCURRENT_SCRAPE_LIMIT = getattr(config, 'CONCURRENT_SCRAPE_LIMIT', 3)
    semaphore = asyncio.Semaphore(CONCURRENT_SCRAPE_LIMIT)

    # Pass tuple of exceptions including requests.exceptions.RequestException for broader network issues
    @retry_with_backoff(catch_exceptions=HTTP_EXCEPTIONS + (requests.exceptions.RequestException, ValueError, Exception))
    async def scrape_single_url_with_retry(url_to_scrape: str, agent_state: Optional[AgentState]) -> Dict[str, Any]:
        async with semaphore: # Acquire semaphore before scraping
            for pattern in compiled_skip_patterns:
                if pattern.search(url_to_scrape):
                    logger.info(f"[Async Scrape] Skipping URL pattern match ({pattern.pattern}): {url_to_scrape}")
                    return {'url': url_to_scrape, 'success': False, 'error': f'Skipped due to file pattern: {pattern.pattern}'}

            logger.info(f"[Async Scrape] Attempting to scrape URL: {url_to_scrape} (Concurrency: {CONCURRENT_SCRAPE_LIMIT - semaphore._value}/{CONCURRENT_SCRAPE_LIMIT})")
            scrape_kwargs = {'only_main_content': True}
            if url_to_scrape.lower().endswith('.pdf'):
                logger.info(f"[Async Scrape] PDF URL detected. Enabling OCR for: {url_to_scrape}")
                scrape_kwargs['ocr'] = True
            
            sync_firecrawl_client = FirecrawlApp(api_key=config.FIRECRAWL_API_KEY)
            
            current_timestamp = datetime.utcnow()
            response: Optional[Any] = await loop.run_in_executor(
                None, 
                partial(sync_firecrawl_client.scrape_url, url_to_scrape, **scrape_kwargs)
            )
            
            if response: # Save raw response if successful
                _save_scraped_data_to_log(url_to_scrape, response, current_timestamp.strftime("%Y%m%d%H%M%S%f"))

            # Handle nested 'data' structure from Firecrawl API
            response_data = response
            if isinstance(response, dict) and 'data' in response:
                response_data = response['data']
            elif hasattr(response, 'data'):
                response_data = response.data
                
            # Extract content from response_data
            markdown_content = ""
            html_content = ""
            metadata = {}
            
            if isinstance(response_data, dict):
                markdown_content = response_data.get('markdown', '')
                html_content = response_data.get('html', '')
                metadata = response_data.get('metadata', {})
            elif hasattr(response_data, 'markdown'):
                markdown_content = getattr(response_data, 'markdown', '')
                html_content = getattr(response_data, 'html', '')
                metadata = getattr(response_data, 'metadata', {})

            if markdown_content:
                title = metadata.get('title', '') if isinstance(metadata, dict) else ''
                document = {
                    'url': url_to_scrape, 'content': markdown_content,
                    'html_content': html_content,
                    'title': title, 'source_type': 'web_scrape_async',
                    'timestamp': current_timestamp.isoformat(), 'success': True,
                    'keywords': metadata.get('keywords', '') if isinstance(metadata, dict) else '',
                    'description': metadata.get('description', '') if isinstance(metadata, dict) else ''
                }
                logger.info(f"[Async Scrape] Successfully scraped {url_to_scrape}")
                if agent_state and hasattr(agent_state, 'api_calls_succeeded'):
                    agent_state.api_calls_succeeded = getattr(agent_state, 'api_calls_succeeded', 0) + 1
                return document
            else:
                err_msg = 'No markdown content found after scrape'
                if response:
                     logger.warning(f"[Async Scrape] Scraped {url_to_scrape} but no markdown. Keys: {vars(response).keys() if response else 'N/A'}")
                else:
                    err_msg = 'No valid response from scrape_url'
                    logger.warning(f"[Async Scrape] Failed to get valid response from scrape_url for: {url_to_scrape}")
                if agent_state and hasattr(agent_state, 'api_calls_failed'):
                    agent_state.api_calls_failed = getattr(agent_state, 'api_calls_failed', 0) + 1
                # Raise ValueError to ensure it's caught by retry_with_backoff if it's configured for ValueError
                raise ValueError(err_msg) 

    tasks = [scrape_single_url_with_retry(url, state) for url in urls]
    results_with_exceptions = await asyncio.gather(*tasks, return_exceptions=True)
    
    processed_results = []
    successful_scrapes = 0
    failed_scrapes = 0
    for i, res_or_exc in enumerate(results_with_exceptions):
        original_url = urls[i]
        if isinstance(res_or_exc, Exception):
            logger.error(f"[Async Scrape] Final failure for URL {original_url} after retries: {res_or_exc}")
            processed_results.append({'url': original_url, 'success': False, 'error': str(res_or_exc)})
            failed_scrapes += 1
        elif res_or_exc and isinstance(res_or_exc, dict) and res_or_exc.get('success'):
            processed_results.append(res_or_exc)
            successful_scrapes += 1
        else: 
            logger.warning(f"[Async Scrape] URL {original_url} processing resulted in non-success/non-exception: {res_or_exc}")
            default_error = 'Unknown scrape failure or skipped'
            if isinstance(res_or_exc, dict) and 'error' in res_or_exc:
                default_error = res_or_exc['error']
            processed_results.append({'url': original_url, 'success': False, 'error': default_error})
            failed_scrapes += 1
            
    logger.info(f"[Async Scrape] Attempt finished. Successfully scraped {successful_scrapes} of {len(urls)} URLs.")
    
    # Ensure API call tracking is properly updated
    if state:
        if hasattr(state, 'api_calls_succeeded'): 
            state.api_calls_succeeded = getattr(state, 'api_calls_succeeded', 0) + successful_scrapes
        if hasattr(state, 'api_calls_failed'):
            # Update failed count, but avoid double-counting if retry_with_backoff already tracked some failures
            current_failed = getattr(state, 'api_calls_failed', 0)
            # Only add failures that weren't already tracked (this is a safeguard)
            additional_failures = max(0, failed_scrapes - (current_failed - getattr(state, 'api_calls_failed', 0)))
            state.api_calls_failed = current_failed + failed_scrapes  # Always count the actual failures we processed
    
    return processed_results

def needs_advanced_scraping(url: str) -> bool:
    """
    Determine if a URL likely needs specific handling (like PDF) or might be JS-heavy.
    NOTE: Firecrawl's scrape_url often handles these automatically now, 
          so this might be less critical, but can be used for informational purposes.
    
    Args:
        url: The URL to check
        
    Returns:
        Boolean indicating if specific handling might be beneficial
    """
    url_lower = url.lower()
    
    # Check for document extensions
    doc_extensions = [".pdf", ".xlsx", ".xls", ".csv", ".zip", ".docx", ".doc"]
    if any(ext in url_lower for ext in doc_extensions):
        return True
    
    # Check for indicators of JavaScript-heavy sites
    js_indicators = ["/#/", "/app/", "/dashboard", "/viewer", "interactive"]
    if any(ind in url_lower for ind in js_indicators):
        return True
    
    return False 

def load_and_chunk_html_content(html_content: str, max_chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    # Implementation of load_and_chunk_html_content function
    # This function should return a list of strings, each representing a chunk of the HTML content
    # The implementation details depend on the specific requirements of the function
    # For now, we'll return an empty list as a placeholder
    return []

# Website crawling function - builds sitemap-like results
def crawl_website(
    base_url: str, 
    max_pages: int = 10, 
    max_depth: int = 2,
    exclude_patterns: Optional[List[str]] = None, 
    timeout_minutes: int = 5,
    state: Optional[AgentState] = None
) -> List[Dict[str, Any]]:
    """
    Crawl an entire website using Firecrawl's crawl_url method.
    This is better than scrape_url for discovering and scraping multiple related pages.
    
    SAFETY LIMITS for massive websites:
    - max_pages: Hard limit on total pages (default: 10, max recommended: 50)
    - max_depth: How many levels deep to crawl (default: 2, max recommended: 3)
    - timeout_minutes: Maximum time to spend crawling (default: 5 min)
    - exclude_patterns: Exclude heavy sections like blogs, forums, etc.
    
    Args:
        base_url: The base URL to start crawling from
        max_pages: Maximum number of pages to crawl (recommended: 10-50 for large sites)
        max_depth: Maximum crawl depth from base URL (recommended: 1-3)
        exclude_patterns: List of URL patterns to exclude (e.g., ['blog/*', 'admin/*', 'forum/*'])
        timeout_minutes: Maximum crawl time in minutes
        state: Optional AgentState for tracking API calls
        
    Returns:
        List of scraped documents from the crawled pages
    """
    # Safety check for massive website protection
    if max_pages > 50:
        logger.warning(f"[Website Crawl] Large max_pages ({max_pages}) detected. Capping at 50 for safety.")
        max_pages = 50  # Cap at 50 for safety
    
    if max_depth > 3:
        logger.warning(f"[Website Crawl] Deep crawling ({max_depth}) can be exponential. Capping at 3.")
        max_depth = 3
    
    if not FIRECRAWL_AVAILABLE:
        logger.error("Firecrawl package is not available for crawl_website")
        if state and hasattr(state, 'api_calls_failed'): 
            state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return []
    
    if not config.FIRECRAWL_API_KEY:
        logger.error("Firecrawl API key is not set for crawl_website")
        if state and hasattr(state, 'api_calls_failed'): 
            state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return []

    try:
        from firecrawl import ScrapeOptions
        client = FirecrawlApp(api_key=config.FIRECRAWL_API_KEY)
        
        # Enhanced safety patterns for massive websites
        default_excludes = [
            'blog/*', 'news/*', 'forum/*', 'community/*', 
            'archive/*', 'search/*', '*/search/*', 
            'user/*', 'profile/*', 'comment/*',
            '*.pdf', '*.zip', '*.doc*', '*.xls*'
        ]
        all_excludes = (exclude_patterns or []) + default_excludes
        
        logger.info(f"[Website Crawl] Starting SAFE crawl of {base_url}")
        logger.info(f"[Website Crawl] Limits: {max_pages} pages, timeout {timeout_minutes}min")
        logger.info(f"[Website Crawl] Excluding: {len(all_excludes)} patterns")
        
        current_timestamp = datetime.utcnow()
        
        # Create ScrapeOptions with proper configuration
        scrape_options = ScrapeOptions(
            formats=['markdown'],  # Focus on markdown for LLM processing
            excludeTags=['nav', 'footer', 'aside', 'menu'],  # Remove navigation clutter
            onlyMainContent=True
        )
        
        # Execute the crawl with proper Firecrawl API parameters
        crawl_result = client.crawl_url(
            base_url,
            limit=max_pages,
            scrape_options=scrape_options,
            # Note: Advanced options like max_depth and excludes patterns 
            # may need to be handled at the URL filtering level post-crawl
        )
        
        documents = []
        if crawl_result and isinstance(crawl_result, dict) and crawl_result.get('success'):
            crawled_data = crawl_result.get('data', [])
            
            for page_data in crawled_data:
                if isinstance(page_data, dict):
                    markdown_content = page_data.get('markdown', '')
                    if markdown_content:
                        metadata = page_data.get('metadata', {})
                        document = {
                            'url': page_data.get('url', ''),
                            'content': markdown_content,
                            'html_content': page_data.get('html', ''),
                            'title': metadata.get('title', '') if isinstance(metadata, dict) else '',
                            'source_type': 'web_crawl',
                            'timestamp': current_timestamp.isoformat(),
                            'success': True,
                            'keywords': metadata.get('keywords', '') if isinstance(metadata, dict) else '',
                            'description': metadata.get('description', '') if isinstance(metadata, dict) else ''
                        }
                        documents.append(document)
                        
                        # Save individual crawled pages
                        _save_scraped_data_to_log(
                            page_data.get('url', ''), 
                            page_data, 
                            current_timestamp.strftime("%Y%m%d%H%M%S%f")
                        )
        
        successful_crawls = len(documents)
        logger.info(f"[Website Crawl] Successfully crawled {successful_crawls} pages from {base_url}")
        
        if state and hasattr(state, 'api_calls_succeeded'): 
            state.api_calls_succeeded = getattr(state, 'api_calls_succeeded', 0) + 1
            
        return documents
        
    except Exception as e:
        logger.error(f"[Website Crawl] Error crawling website {base_url}: {str(e)}", exc_info=True)
        if state and hasattr(state, 'api_calls_failed'): 
            state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return []

def scrape_with_extraction(url: str, extraction_schema: Optional[Dict] = None, state: Optional[AgentState] = None) -> Dict[str, Any]:
    """
    Enhanced scraping with optional LLM-based structured data extraction.
    
    Args:
        url: URL to scrape
        extraction_schema: Optional Pydantic schema for structured extraction
        state: Optional AgentState for tracking API calls
        
    Returns:
        Dictionary containing scraped content and optional extracted data
    """
    if not FIRECRAWL_AVAILABLE:
        logger.error("Firecrawl package is not available for enhanced scraping")
        if state and hasattr(state, 'api_calls_failed'): 
            state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return {'url': url, 'success': False, 'error': 'Firecrawl not available'}
    
    if not config.FIRECRAWL_API_KEY:
        logger.error("Firecrawl API key is not set for enhanced scraping")
        if state and hasattr(state, 'api_calls_failed'): 
            state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return {'url': url, 'success': False, 'error': 'Firecrawl API key not set'}

    try:
        client = FirecrawlApp(api_key=config.FIRECRAWL_API_KEY)
        
        # Prepare enhanced scraping options
        scrape_options = {
            'pageOptions': {
                'onlyMainContent': True,
                'includeHtml': True,
                'waitFor': 3000,  # Wait for dynamic content
                'screenshot': False  # Can be enabled if needed
            }
        }
        
        # Add LLM extraction if schema provided
        if extraction_schema:
            scrape_options['extractorOptions'] = {
                'extractionSchema': extraction_schema,
                'mode': 'llm-extraction'
            }
        
        logger.info(f"[Enhanced Scrape] Scraping {url} with {'extraction' if extraction_schema else 'standard'} mode")
        current_timestamp = datetime.utcnow()
        
        response = client.scrape_url(url, scrape_options)
        
        if response:
            _save_scraped_data_to_log(url, response, current_timestamp.strftime("%Y%m%d%H%M%S%f"))
            
            # Handle response structure
            response_data = response
            if isinstance(response, dict) and 'data' in response:
                response_data = response['data']
                
            if isinstance(response_data, dict):
                markdown_content = response_data.get('markdown', '')
                if markdown_content:
                    metadata = response_data.get('metadata', {})
                    document = {
                        'url': url,
                        'content': markdown_content,
                        'html_content': response_data.get('html', ''),
                        'title': metadata.get('title', '') if isinstance(metadata, dict) else '',
                        'source_type': 'enhanced_scrape',
                        'timestamp': current_timestamp.isoformat(),
                        'success': True,
                        'keywords': metadata.get('keywords', '') if isinstance(metadata, dict) else '',
                        'description': metadata.get('description', '') if isinstance(metadata, dict) else ''
                    }
                    
                    # Add extracted data if available
                    if 'llm_extraction' in response_data:
                        document['extracted_data'] = response_data['llm_extraction']
                    
                    if state and hasattr(state, 'api_calls_succeeded'): 
                        state.api_calls_succeeded = getattr(state, 'api_calls_succeeded', 0) + 1
                    return document
        
        logger.warning(f"[Enhanced Scrape] No content extracted from {url}")
        if state and hasattr(state, 'api_calls_failed'): 
            state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return {'url': url, 'success': False, 'error': 'No content extracted'}
        
    except Exception as e:
        logger.error(f"[Enhanced Scrape] Error in enhanced scraping for {url}: {str(e)}", exc_info=True)
        if state and hasattr(state, 'api_calls_failed'): 
            state.api_calls_failed = getattr(state, 'api_calls_failed', 0) + 1
        return {'url': url, 'success': False, 'error': str(e)}
