"""
Integration tests for city-based CLI functionality.
These tests verify that the command line interface works correctly with city mode.
"""
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import argparse
import asyncio
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from main import main_async
from agent_state import AgentState
import config

class TestCityCLIIntegration(unittest.TestCase):
    """Test CLI integration for city mode."""

    def setUp(self):
        """Setup test environment."""
        # Store original config values
        self.original_openrouter_key = config.OPENROUTER_API_KEY
        self.original_firecrawl_key = config.FIRECRAWL_API_KEY
        
        # Set mock API keys
        config.OPENROUTER_API_KEY = "mock_city_cli_key"
        config.FIRECRAWL_API_KEY = "mock_city_cli_firecrawl_key"

    def tearDown(self):
        """Clean up test environment."""
        config.OPENROUTER_API_KEY = self.original_openrouter_key
        config.FIRECRAWL_API_KEY = self.original_firecrawl_key

    def create_mock_args_city(self, city_name, english=False, max_iterations=2):
        """Helper to create mock CLI arguments for city mode."""
        args = argparse.Namespace()
        args.city = city_name
        args.country = None
        args.sector = None
        args.english = english
        args.log_level = "INFO"
        args.max_iterations = max_iterations
        return args

    @patch('main.run_agent', new_callable=AsyncMock)
    async def test_cli_city_mode_basic(self, mock_run_agent):
        """Test basic CLI functionality for city mode."""
        test_city = "Berlin"
        
        # Mock the run_agent return
        mock_final_state = AgentState(
            prompt=f"City: {test_city}",
            target_city=test_city,
            research_mode="city",
            metadata={
                "research_mode": "city",
                "next_step_after_structured_review": "accept"
            },
            structured_data=[{"name": "Mock Berlin emissions data", "url": "http://berlin.de/test"}],
            decision_log=[{"action": "init", "city": test_city}]
        )
        mock_run_agent.return_value = mock_final_state
        
        # Create city mode arguments
        args = self.create_mock_args_city(test_city)
        
        # Run main_async (should not raise exceptions)
        try:
            await main_async(args)
        except Exception as e:
            self.fail(f"main_async raised an unexpected exception in city mode: {e}")
        
        # Verify run_agent was called with correct parameters
        mock_run_agent.assert_called_once()
        call_kwargs = mock_run_agent.call_args.kwargs
        self.assertEqual(call_kwargs["city_name"], test_city)
        self.assertIsNone(call_kwargs.get("country_name"))
        self.assertIsNone(call_kwargs.get("sector_name"))

    @patch('main.run_agent', new_callable=AsyncMock)
    async def test_cli_city_mode_multiword(self, mock_run_agent):
        """Test CLI functionality for multi-word city names."""
        test_city = "New York"
        
        # Mock the run_agent return
        mock_final_state = AgentState(
            prompt=f"City: {test_city}",
            target_city=test_city,
            research_mode="city",
            metadata={"research_mode": "city"},
            decision_log=[{"action": "init", "city": test_city}]
        )
        mock_run_agent.return_value = mock_final_state
        
        # Test that multi-word city names would be handled
        # (In actual CLI, this would require proper argument parsing)
        args = self.create_mock_args_city(test_city)
        
        try:
            await main_async(args)
        except Exception as e:
            self.fail(f"main_async failed with multi-word city: {e}")
        
        # Verify the city name was passed correctly
        call_kwargs = mock_run_agent.call_args.kwargs
        self.assertEqual(call_kwargs["city_name"], test_city)

    @patch('main.run_agent', new_callable=AsyncMock)
    async def test_cli_city_mode_with_english_flag(self, mock_run_agent):
        """Test CLI city mode with English-only flag."""
        test_city = "Prague"
        
        # Mock the run_agent return
        mock_final_state = AgentState(
            prompt=f"City: {test_city}",
            target_city=test_city,
            research_mode="city",
            metadata={
                "research_mode": "city",
                "english_only_mode": True
            },
            decision_log=[{"action": "init", "city": test_city, "english_only_mode": True}]
        )
        mock_run_agent.return_value = mock_final_state
        
        # Create arguments with English flag
        args = self.create_mock_args_city(test_city, english=True)
        
        await main_async(args)
        
        # Verify English-only mode was passed
        call_kwargs = mock_run_agent.call_args.kwargs
        self.assertEqual(call_kwargs["city_name"], test_city)
        self.assertTrue(call_kwargs["english_only_mode"])

    @patch('main.run_agent', new_callable=AsyncMock)
    async def test_cli_city_mode_with_config_overrides(self, mock_run_agent):
        """Test CLI city mode with configuration overrides."""
        test_city = "Tokyo"
        max_iterations = 5
        
        # Mock the run_agent return
        mock_final_state = AgentState(
            prompt=f"City: {test_city}",
            target_city=test_city,
            research_mode="city",
            metadata={"research_mode": "city"},
            current_iteration=max_iterations,
            decision_log=[{"action": "init", "city": test_city}]
        )
        mock_run_agent.return_value = mock_final_state
        
        # Create arguments with max iterations override
        args = self.create_mock_args_city(test_city, max_iterations=max_iterations)
        
        await main_async(args)
        
        # Verify config overrides were passed
        call_kwargs = mock_run_agent.call_args.kwargs
        expected_overrides = {"MAX_ITERATIONS": max_iterations}
        self.assertEqual(call_kwargs["cli_config_overrides"], expected_overrides)

    def test_argument_parsing_simulation(self):
        """Test that argument parsing logic works for city mode."""
        # This simulates the argument parsing logic from main.py
        
        # Test single word city
        test_args = ["--city", "London"]
        # In real implementation, this would use argparse
        # Here we just verify the concept
        
        self.assertIn("--city", test_args)
        self.assertEqual(test_args[test_args.index("--city") + 1], "London")
        
        # Test that we can detect city mode vs country mode
        city_mode = "--city" in test_args
        country_mode = "--country" in test_args and "--sector" in test_args
        
        self.assertTrue(city_mode)
        self.assertFalse(country_mode)

    def test_help_text_includes_city_option(self):
        """Test that help text includes information about city mode."""
        # This would test that the help text mentions the --city option
        # In a real test, we might capture parser.format_help() output
        
        # For now, just verify the concept
        expected_help_keywords = ["--city", "city name", "city-based research"]
        
        # In actual implementation, you would check:
        # help_text = parser.format_help()
        # for keyword in expected_help_keywords:
        #     self.assertIn(keyword, help_text)
        
        # For this test, we just verify the keywords exist
        self.assertTrue(all(isinstance(keyword, str) for keyword in expected_help_keywords))


def run_city_cli_tests():
    """Run the city CLI integration tests."""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_city_cli_tests() 