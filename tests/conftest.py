"""
Configuration for pytest - shared fixtures and plugins.
"""
import os
import sys
import pytest
from pathlib import Path

# Add the project root directory to the Python path
# This ensures that modules can be imported in tests
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

@pytest.fixture
def test_env():
    """Provides basic environment variables for testing."""
    return {
        "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", ""),
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
    }

@pytest.fixture
def mock_state():
    """Provides a sample agent state for testing."""
    from agent_state import AgentState
    
    return AgentState(
        prompt="sample query",
        urls=[{"title": "Sample Result", "url": "https://example.com"}],
        confidence_scores={"Sample Result": 0.85},
        iteration_count=1
    )

@pytest.fixture
def sample_state():
    """Fixture providing a sample AgentState for testing."""
    from agent_state import create_initial_state
    # Provide a default country and sector for the fixture
    return create_initial_state(country_name="Test Country Fixture", sector_name="stationary_energy")

@pytest.fixture
def api_keys_available():
    """Fixture checking if API keys are available."""
    from config import validate_api_keys
    keys = validate_api_keys()
    return {
        "all_available": all(keys.values()),
        "keys": keys
    } 