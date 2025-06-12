"""
Tests for Firecrawl API functionality.
"""
import pytest
import logging
from typing import Any, Dict, Optional, Union

# Import project modules (handled by conftest.py)
import config

# Get a logger instance
logger = logging.getLogger(__name__)

# Check if firecrawl package is installed
try:
    from firecrawl.firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    FirecrawlApp = None

@pytest.mark.skipif(
    not FIRECRAWL_AVAILABLE or not config.validate_api_keys().get("firecrawl", False),
    reason="Firecrawl API key is not set or firecrawl package is not installed"
)
def test_firecrawl_scrape():
    """
    Test Firecrawl by scraping example.com.
    Verifies content contains 'Example Domain'.
    """
    if not FIRECRAWL_AVAILABLE:
        pytest.skip("Firecrawl package is not installed")
        
    if not config.validate_api_keys().get("firecrawl", False):
        pytest.skip("Firecrawl API key is not set")
    
    # Safety check, though the skipif should prevent this
    if FirecrawlApp is None:
        pytest.skip("FirecrawlApp class is not available")
    
    # Initialize the Firecrawl client
    client = FirecrawlApp(api_key=config.FIRECRAWL_API_KEY)
    
    # Test URL to scrape
    test_url = "https://example.com"
    
    # Expected content (case insensitive)
    expected_content = "example domain"
    
    # Use the scrape_url method to get the content for a specific URL
    response = client.scrape_url(test_url)

    # Verify that the response has content and it matches expected
    assert response is not None, "Firecrawl scrape_url returned None"
    # The response from scrape_url is an object, typically with a .content or .markdown attribute
    # Check for common attributes that hold the textual content.
    # Firecrawl's ScrapeResponse has .markdown and .html.
    # We expect "example domain" to be in one of these.
    content_to_check = ""
    if hasattr(response, 'markdown') and response.markdown:
        content_to_check = response.markdown
    elif hasattr(response, 'html') and response.html:
        content_to_check = response.html

    assert content_to_check, "No suitable content (markdown or html) found in Firecrawl response for example.com"
    assert expected_content.lower() in content_to_check.lower(), \
        f"Expected '{expected_content}' not found in scraped content: {content_to_check[:500]}..."

    logger.info("Firecrawl scrape test completed successfully.")

def test_firecrawl_api_key_loaded():
    """Test that the Firecrawl API key is loaded."""
    assert hasattr(config, "FIRECRAWL_API_KEY"), "FIRECRAWL_API_KEY not found in config"

if __name__ == "__main__":
    print("Running Firecrawl tests directly...")
    pytest.main(["-xvs", __file__]) 