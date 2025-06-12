import asyncio
import pytest
import logging
from unittest.mock import patch, MagicMock, call
from datetime import datetime
import os
import config

# Test modules
from agents.utils.scraping import (
    scrape_urls_async, 
    scrape_urls_sync, 
    crawl_website,
    needs_advanced_scraping
)
from agent_state import AgentState, create_initial_state

logger = logging.getLogger(__name__)


# --- REAL INTEGRATION TESTS (2-PAGE LIMITS) ---

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_scrape_urls_async_integration():
    """
    REAL INTEGRATION TEST: Test actual scrape_urls_async with Firecrawl API.
    Limited to 1 URL for safety.
    """
    pytest.importorskip("firecrawl", reason="Firecrawl not available for integration test")
    
    if not config.FIRECRAWL_API_KEY:
        pytest.skip("FIRECRAWL_API_KEY not set - skipping real integration test")
    
    # Test with a simple, reliable URL
    test_urls = ["https://httpbin.org/html"]
    
    logger.info("=== REAL SCRAPE_URLS_ASYNC INTEGRATION TEST ===")
    
    # Create a test state for tracking
    state = create_initial_state("TestCountry", "test_sector")
    
    # Call real function
    results = await scrape_urls_async(test_urls, state)
    
    # Verify results
    assert isinstance(results, list), "Should return a list"
    assert len(results) == 1, "Should have exactly one result"
    
    result = results[0]
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "url" in result, "Should have URL"
    assert "success" in result, "Should have success status"
    
    if result["success"]:
        assert "content" in result, "Successful result should have content"
        assert len(result["content"]) > 0, "Content should not be empty"
        assert "source_type" in result, "Should have source_type"
        assert result["source_type"] == "web_scrape_async", "Should be async scrape"
        
        # Verify state tracking
        assert state.api_calls_succeeded >= 1, "Should track successful calls"
        
        logger.info(f"✅ Real async scrape test PASSED")
        logger.info(f"Content length: {len(result['content'])} characters")
    else:
        logger.warning(f"⚠️ Scrape failed: {result.get('error', 'Unknown error')}")


@pytest.mark.integration 
def test_real_scrape_urls_sync_integration():
    """
    REAL INTEGRATION TEST: Test actual scrape_urls_sync with Firecrawl API.
    Limited to 1 URL for safety.
    """
    pytest.importorskip("firecrawl", reason="Firecrawl not available for integration test")
    
    if not config.FIRECRAWL_API_KEY:
        pytest.skip("FIRECRAWL_API_KEY not set - skipping real integration test")
    
    # Test with a simple, reliable URL
    test_urls = ["https://httpbin.org/html"]
    
    logger.info("=== REAL SCRAPE_URLS_SYNC INTEGRATION TEST ===")
    
    # Create a test state for tracking
    state = create_initial_state("TestCountry", "test_sector")
    
    # Call real function
    results = scrape_urls_sync(test_urls, state)
    
    # Verify results
    assert isinstance(results, list), "Should return a list"
    assert len(results) == 1, "Should have exactly one result"
    
    result = results[0]
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "url" in result, "Should have URL"
    assert "success" in result, "Should have success status"
    
    if result["success"]:
        assert "content" in result, "Successful result should have content"
        assert len(result["content"]) > 0, "Content should not be empty"
        assert "source_type" in result, "Should have source_type"
        assert result["source_type"] == "web_scrape_sync", "Should be sync scrape"
        
        # Verify state tracking
        assert state.api_calls_succeeded >= 1, "Should track successful calls"
        
        logger.info(f"✅ Real sync scrape test PASSED")
        logger.info(f"Content length: {len(result['content'])} characters")
    else:
        logger.warning(f"⚠️ Scrape failed: {result.get('error', 'Unknown error')}")


@pytest.mark.integration
def test_real_crawl_website_integration_strict_limits():
    """
    REAL INTEGRATION TEST: Test actual crawl_website with Firecrawl API.
    STRICT 2-page maximum limit for safety.
    """
    pytest.importorskip("firecrawl", reason="Firecrawl not available for integration test")
    
    if not config.FIRECRAWL_API_KEY:
        pytest.skip("FIRECRAWL_API_KEY not set - skipping real integration test")
    
    # Test with a small, reliable website
    test_url = "https://httpbin.org"
    
    logger.info("=== REAL CRAWL_WEBSITE INTEGRATION TEST ===")
    logger.info(f"Testing crawl of {test_url} with STRICT 2-page limit")
    
    # Create a test state for tracking
    state = create_initial_state("TestCountry", "test_sector")
    
    # Call real function with STRICT safety limits
    results = crawl_website(
        base_url=test_url,
        max_pages=2,  # STRICT LIMIT: Maximum 2 pages
        timeout_minutes=1,  # STRICT TIMEOUT: 1 minute max
        exclude_patterns=['*.pdf', '*.zip', 'admin/*', 'api/*'],
        state=state
    )
    
    # Verify results
    assert isinstance(results, list), "Should return a list"
    assert len(results) <= 2, f"SAFETY VIOLATION: Got {len(results)} pages, expected ≤ 2"
    
    if results:  # If any pages were crawled
        for i, result in enumerate(results):
            assert isinstance(result, dict), f"Result {i} should be a dictionary"
            assert "url" in result, f"Result {i} should have URL"
            assert "success" in result, f"Result {i} should have success status"
            assert result["success"] is True, f"Result {i} should be successful"
            assert "content" in result, f"Result {i} should have content"
            assert len(result["content"]) > 0, f"Result {i} content should not be empty"
            assert "source_type" in result, f"Result {i} should have source_type"
            assert result["source_type"] == "web_crawl", f"Result {i} should be web_crawl type"
            
        # Verify state tracking
        assert state.api_calls_succeeded >= 1, "Should track successful API calls"
        
        logger.info(f"✅ Real crawl integration test PASSED: {len(results)} pages crawled")
        logger.info(f"URLs crawled: {[r['url'] for r in results]}")
    else:
        logger.warning("⚠️ No pages were crawled - this may be expected for some sites")


@pytest.mark.integration
def test_real_crawl_website_safety_enforcement():
    """
    REAL INTEGRATION TEST: Test that safety limits are strictly enforced.
    """
    pytest.importorskip("firecrawl", reason="Firecrawl not available for integration test")
    
    if not config.FIRECRAWL_API_KEY:
        pytest.skip("FIRECRAWL_API_KEY not set - skipping real integration test")
    
    test_url = "https://httpbin.org"
    
    logger.info("=== TESTING CRAWL SAFETY ENFORCEMENT ===")
    
    # Test 1: Single page limit enforcement
    results_1 = crawl_website(
        base_url=test_url,
        max_pages=1,  # STRICT: Only 1 page
        timeout_minutes=1
    )
    assert len(results_1) <= 1, f"1-page limit violated: got {len(results_1)}"
    
    # Test 2: Large max_pages should be capped automatically
    # The function should cap it at 50 internally
    results_large = crawl_website(
        base_url=test_url,
        max_pages=100,  # This should be automatically capped
        timeout_minutes=1
    )
    # Don't check exact limit since it depends on the site, but verify it's reasonable
    assert len(results_large) <= 50, f"Large limit not properly capped: got {len(results_large)}"
    
    logger.info(f"✅ Safety enforcement PASSED:")
    logger.info(f"  - 1-page test: {len(results_1)} pages")
    logger.info(f"  - Large limit test: {len(results_large)} pages (should be ≤ 50)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_scraping_error_handling():
    """
    REAL INTEGRATION TEST: Test error handling with invalid URLs.
    """
    pytest.importorskip("firecrawl", reason="Firecrawl not available for integration test")
    
    if not config.FIRECRAWL_API_KEY:
        pytest.skip("FIRECRAWL_API_KEY not set - skipping real integration test")
    
    logger.info("=== TESTING REAL ERROR HANDLING ===")
    
    # Test with invalid URLs
    invalid_urls = ["https://this-domain-does-not-exist-12345.com"]
    
    state = create_initial_state("TestCountry", "test_sector")
    
    # Test async scraping with invalid URL
    results = await scrape_urls_async(invalid_urls, state)
    
    assert isinstance(results, list), "Should return a list even for errors"
    assert len(results) == 1, "Should have one result per URL"
    
    result = results[0]
    assert result["success"] is False, "Should mark invalid URL as failed"
    assert "error" in result, "Should have error message"
    assert "url" in result, "Should still have the URL"
    
    # Verify error tracking
    assert state.api_calls_failed >= 1, "Should track failed calls"
    
    logger.info(f"✅ Error handling test PASSED: {result['error']}")


# --- UNIT TESTS WITH MOCKS --- 