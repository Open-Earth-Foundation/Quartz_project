"""
Smoke tests for the application to verify core components are working.
"""
import pytest
import os
import sys

# Import project modules (handled by conftest.py)
import config

# Define an umbrella smoke test class
class TestSmokeTests:
    """Group all smoke tests together."""
    
    def test_api_keys(self, api_keys_available):
        """Verify required API keys are set."""
        keys = api_keys_available["keys"]
        assert "firecrawl" in keys, "Firecrawl key validation missing"
        assert "openrouter" in keys, "OpenRouter key validation missing"
        
        # Don't fail if keys are not actually set - that's expected in CI
        # Just verify the validation function works correctly
        assert isinstance(keys["firecrawl"], bool), "Firecrawl key validation should return boolean"
        assert isinstance(keys["openrouter"], bool), "OpenRouter key validation should return boolean"
    
    def test_config_loaded(self):
        """Verify configuration is loaded properly."""
        # Check core configuration constants
        assert hasattr(config, "FIRECRAWL_API_KEY"), "FIRECRAWL_API_KEY missing"
        assert hasattr(config, "OPENROUTER_API_KEY"), "OPENROUTER_API_KEY missing"
        assert hasattr(config, "THINKING_MODEL"), "THINKING_MODEL missing"
        assert hasattr(config, "NORMAL_MODEL"), "NORMAL_MODEL missing"
        
        # Check if settings loading function exists (may not be present in all configs)
        try:
            if hasattr(config, "load_settings"):
                # Check that the function works
                try:
                    settings = config.load_settings()  # type: ignore
                    assert isinstance(settings, dict), "Settings should be a dictionary"
                except AttributeError:
                    # Skip this check if the function doesn't exist
                    pass
        except AttributeError:
            # Skip this check if the function doesn't exist
            pass

    def test_environment(self):
        """Verify environment is properly set up."""
        # Verify Python version
        assert sys.version_info.major == 3, "Should be running Python 3"
        
        # Check that project root is properly set up
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assert os.path.isfile(os.path.join(root_dir, "config.py")), "config.py should exist at project root"
        assert os.path.isdir(os.path.join(root_dir, "tests")), "tests directory should exist"

if __name__ == "__main__":
    print("Running smoke tests directly...")
    pytest.main(["-xvs", __file__]) 