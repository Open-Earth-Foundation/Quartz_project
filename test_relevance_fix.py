#!/usr/bin/env python3
"""
Test script to verify the relevance checker fix for heatwave hazard data.
"""

import asyncio
import sys
import os
from openai import AsyncOpenAI

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.relevance_checker import check_url_relevance_async, fallback_relevance_check
import config

async def test_heatwave_relevance():
    """Test the relevance checker with heatwave-related URLs."""
    
    # Test data - URLs that should be relevant for heatwave hazards
    test_cases = [
        {
            "url": "https://www.kaggle.com/datasets/berkeleyearth/climate-change-earth-surface-temperature-data",
            "title": "Climate Change: Earth Surface Temperature Data",
            "snippet": "The dataset focuses on earth surface temperature data, including daily maximum temperature records and temperature anomalies for climate analysis."
        },
        {
            "url": "https://climate.copernicus.eu/global-climate-highlights-2024",
            "title": "Global Climate Highlights 2024",
            "snippet": "Global temperature records and extreme heat events, including heatwave frequency and temperature percentiles for climate monitoring."
        },
        {
            "url": "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series",
            "title": "Climate at a Glance: Global Time Series",
            "snippet": "Global temperature anomalies and climate data including daily maximum temperature and heat wave indices."
        },
        {
            "url": "https://data.giss.nasa.gov/gistemp/",
            "title": "GISS Surface Temperature Analysis",
            "snippet": "Global temperature analysis with gridded temperature data and temperature extremes for climate research."
        }
    ]
    
    print("Testing Heatwave Relevance Checker Fix")
    print("=" * 50)
    
    # Test with fallback function (no LLM required)
    print("\n1. Testing Fallback Relevance Check:")
    print("-" * 40)
    
    for i, test_case in enumerate(test_cases, 1):
        result = fallback_relevance_check(
            search_result=test_case,
            target_country="Global",
            target_sector="hazards heatwave"
        )
        
        print(f"Test {i}: {test_case['title'][:50]}...")
        print(f"  URL: {test_case['url']}")
        print(f"  Relevant: {result.is_relevant}")
        print(f"  Reason: {result.reason}")
        print()
    
    # Test with LLM if available
    if config.RELEVANCE_CHECK_MODEL and config.OPENROUTER_API_KEY:
        print("\n2. Testing LLM-based Relevance Check:")
        print("-" * 40)
        
        client = AsyncOpenAI(
            base_url=config.OPENROUTER_BASE_URL,
            api_key=config.OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": config.HTTP_REFERER,
                "X-Title": config.SITE_NAME,
            }
        )
        
        for i, test_case in enumerate(test_cases, 1):
            try:
                result = await check_url_relevance_async(
                    search_result=test_case,
                    target_country="Global",
                    target_sector="hazards heatwave",
                    client=client,
                    delay_seconds=1.0
                )
                
                print(f"Test {i}: {test_case['title'][:50]}...")
                print(f"  URL: {test_case['url']}")
                print(f"  Relevant: {result.is_relevant}")
                print(f"  Reason: {result.reason}")
                print()
                
            except Exception as e:
                print(f"Test {i} failed with error: {e}")
                print()
    else:
        print("\n2. LLM-based test skipped (no API key or model configured)")
    
    print("\n3. Testing Context Parsing:")
    print("-" * 40)
    
    from agents.relevance_checker import _parse_ccra_context, _generate_system_prompt
    
    test_contexts = [
        "hazards heatwave",
        "hazards drought", 
        "exposure buildings",
        "vulnerability socioeconomic",
        "emissions transportation"
    ]
    
    for context in test_contexts:
        mode, type_val = _parse_ccra_context(context)
        prompt = _generate_system_prompt(mode, type_val, "Global")
        
        print(f"Context: '{context}'")
        print(f"  Parsed as: mode='{mode}', type='{type_val}'")
        print(f"  System prompt (first 100 chars): {prompt[:100]}...")
        print()

if __name__ == "__main__":
    asyncio.run(test_heatwave_relevance())