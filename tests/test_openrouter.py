"""
Tests for OpenRouter API connectivity with both models.
"""
import pytest

# Import project modules (handled by conftest.py)
import config

# Handle potential import errors
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

def is_valid_openrouter_key():
    """Check if the OpenRouter API key is valid and non-empty."""
    return bool(config.OPENROUTER_API_KEY and config.OPENROUTER_API_KEY != "your_openrouter_api_key_here")

@pytest.mark.skipif(
    not OPENAI_AVAILABLE or not is_valid_openrouter_key(),
    reason="OpenRouter API key is not set, invalid, or openai package is not installed"
)
def test_openrouter_models():
    """
    Test both THINKING_MODEL and NORMAL_MODEL via OpenRouter.
    Verifies that the API responds to simple prompts.
    """
    if not OPENAI_AVAILABLE:
        pytest.skip("OpenAI package is not installed")
    
    if not is_valid_openrouter_key():
        pytest.skip("OpenRouter API key is not set or is invalid")
        
    # Initialize OpenRouter client using the OpenAI SDK
    client = OpenAI(
        base_url=config.OPENROUTER_BASE_URL,
        api_key=config.OPENROUTER_API_KEY,
        default_headers={
            "HTTP-Referer": config.HTTP_REFERER,
            "X-Title": config.SITE_NAME,
        }
    )
    
    # Test the normal model with a simple prompt
    normal_prompt = "Say hello in Polish."
    pytest.skip("Temporarily skipping live OpenRouter model test.")
    normal_response = client.chat.completions.create(
        model=config.NORMAL_MODEL,
        messages=[
            {"role": "user", "content": normal_prompt}
        ],
        temperature=0.7,
        max_tokens=100
    )
    
    # Verify normal model response
    assert normal_response.choices[0].message.content, "Normal model should return a non-empty response"
    
    # Test the thinking model with a reasoning task
    thinking_prompt = "What is the result of 127 * 456? Think step by step."
    thinking_response = client.chat.completions.create(
        model=config.THINKING_MODEL,
        messages=[
            {"role": "user", "content": thinking_prompt}
        ],
        temperature=0.3,
        max_tokens=500
    )
    
    # Verify thinking model response
    assert thinking_response.choices[0].message.content, "Thinking model should return a non-empty response"
    
    # Verify that both models are accessible
    assert normal_response.model.startswith(config.NORMAL_MODEL.split('/')[0]), "Normal model should be accessible"
    assert thinking_response.model.startswith(config.THINKING_MODEL.split('/')[0]), "Thinking model should be accessible"

def test_openrouter_config():
    """Test that OpenRouter configuration is loaded."""
    assert hasattr(config, "OPENROUTER_API_KEY"), "OPENROUTER_API_KEY not found in config"
    assert hasattr(config, "OPENROUTER_BASE_URL"), "OPENROUTER_BASE_URL not found in config"
    assert hasattr(config, "THINKING_MODEL"), "THINKING_MODEL not found in config"
    assert hasattr(config, "NORMAL_MODEL"), "NORMAL_MODEL not found in config"

if __name__ == "__main__":
    print("Running OpenRouter tests directly...")
    pytest.main(["-xvs", __file__]) 