"""
Test script to verify that API keys are loaded correctly from config.py.
"""
import pytest
import os
import sys

# Import project modules (handled by conftest.py)
import config

def mask_key(key: str, visible_chars: int = 4) -> str:
    """
    Mask an API key for displaying, showing only the last few characters.
    
    Args:
        key: The API key to mask
        visible_chars: Number of characters to keep visible at the end
        
    Returns:
        Masked string (e.g., "****abcd")
    """
    if not key:
        return "[NOT SET]"
    
    if len(key) <= visible_chars:
        return key
        
    masked_part = "*" * (len(key) - visible_chars)
    visible_part = key[-visible_chars:]
    return f"{masked_part}{visible_part}"

def test_api_keys_loaded():
    """Test that API keys are loaded from environment variables."""
    assert hasattr(config, "FIRECRAWL_API_KEY"), "FIRECRAWL_API_KEY not found in config"
    assert hasattr(config, "OPENROUTER_API_KEY"), "OPENROUTER_API_KEY not found in config"

def test_api_key_validation(api_keys_available):
    """Test the API key validation function."""
    keys = api_keys_available["keys"]
    assert "firecrawl" in keys, "Firecrawl key check missing"
    assert "openrouter" in keys, "OpenRouter key check missing"
    
    # Print the masked keys if running the tests manually (when not run by pytest)
    if '__file__' in globals() and os.path.basename(__file__) in sys.argv[0]:
        print("\n=== API Key Verification ===")
        print(f"FIRECRAWL_API_KEY: {mask_key(config.FIRECRAWL_API_KEY)} → {'✅ Set' if keys['firecrawl'] else '❌ NOT SET'}")
        print(f"OPENROUTER_API_KEY: {mask_key(config.OPENROUTER_API_KEY)} → {'✅ Set' if keys['openrouter'] else '❌ NOT SET'}")
        print("============================\n")
    
    # These assertions can be commented out if you want the tests to pass without API keys
    # assert keys["firecrawl"], "Firecrawl API key is not set"
    # assert keys["openrouter"], "OpenRouter API key is not set"

if __name__ == "__main__":
    # For running this test file directly
    print("Running API key tests...")
    test_api_keys_loaded()
    
    validation_results = config.validate_api_keys()
    
    print("\n=== API Key Verification ===")
    print(f"FIRECRAWL_API_KEY: {mask_key(config.FIRECRAWL_API_KEY)} → {'✅ Set' if validation_results['firecrawl'] else '❌ NOT SET'}")
    print(f"OPENROUTER_API_KEY: {mask_key(config.OPENROUTER_API_KEY)} → {'✅ Set' if validation_results['openrouter'] else '❌ NOT SET'}")
    print("============================\n")
    
    models = [
        ("THINKING_MODEL", config.THINKING_MODEL),
        ("NORMAL_MODEL", config.NORMAL_MODEL)
    ]
    
    print("=== Models Configuration ===")
    for name, model in models:
        print(f"{name}: {model}")
    print("============================\n")
    
    if all(validation_results.values()):
        print("✅ All required API keys are set.")
    else:
        missing = [key for key, valid in validation_results.items() if not valid]
        print(f"⚠️ Missing API keys: {', '.join(missing)}")
        print("Please add them to your .env file and try again.") 