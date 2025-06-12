"""
Test to demonstrate and verify the city+sector prompt combination functionality.
This will show how the planner combines city and sector prompts.
"""
import unittest
from unittest.mock import patch, MagicMock
import asyncio
from pathlib import Path

# Import project modules
from agent_state import create_initial_state
from agents.planner import planner_node
import config

class TestCityPromptCombination(unittest.TestCase):
    """Test the city+sector prompt combination functionality."""

    def setUp(self):
        """Setup test environment."""
        # Store original config values
        self.original_openrouter_key = config.OPENROUTER_API_KEY
        self.original_firecrawl_key = config.FIRECRAWL_API_KEY
        
        # Set mock API keys
        config.OPENROUTER_API_KEY = "mock_test_key"
        config.FIRECRAWL_API_KEY = "mock_test_firecrawl_key"
        
        # Ensure test configs are available
        config.THINKING_MODEL = config.THINKING_MODEL or "test_model"
        config.STRUCTURED_MODEL = config.STRUCTURED_MODEL or "test_model"
        config.OPENROUTER_BASE_URL = config.OPENROUTER_BASE_URL or "http://localhost:1234"

    def tearDown(self):
        """Clean up test environment."""
        config.OPENROUTER_API_KEY = self.original_openrouter_key
        config.FIRECRAWL_API_KEY = self.original_firecrawl_key

    def test_city_only_state_creation(self):
        """Test creating state for city-only mode."""
        state = create_initial_state(city_name="Berlin")
        
        self.assertEqual(state.target_city, "Berlin")
        self.assertIsNone(state.target_sector)
        self.assertEqual(state.research_mode, "city")
        self.assertEqual(state.prompt, "City: Berlin")
        
        print(f"\n--- City Only Mode ---")
        print(f"Prompt: {state.prompt}")
        print(f"Research Mode: {state.research_mode}")
        print(f"Target City: {state.target_city}")
        print(f"Target Sector: {state.target_sector}")

    def test_city_plus_sector_state_creation(self):
        """Test creating state for city+sector mode."""
        state = create_initial_state(city_name="Berlin", sector_name="stationary_energy")
        
        self.assertEqual(state.target_city, "Berlin")
        self.assertEqual(state.target_sector, "stationary_energy")
        self.assertEqual(state.research_mode, "city")
        self.assertEqual(state.prompt, "City: Berlin, Sector: stationary_energy")
        
        print(f"\n--- City + Sector Mode ---")
        print(f"Prompt: {state.prompt}")
        print(f"Research Mode: {state.research_mode}")
        print(f"Target City: {state.target_city}")
        print(f"Target Sector: {state.target_sector}")

    def test_prompt_loading_logic(self):
        """Test that the correct prompts are loaded for different modes."""
        # Check city prompt exists
        city_prompt_path = Path(__file__).parent.parent / "agents" / "prompts" / "agent1_planner_city.md"
        self.assertTrue(city_prompt_path.exists(), "City prompt should exist")
        
        # Check sector prompt exists
        sector_prompt_path = Path(__file__).parent.parent / "agents" / "prompts" / "stationary_energy.md"
        self.assertTrue(sector_prompt_path.exists(), "Stationary energy sector prompt should exist")
        
        print(f"\n--- Prompt Files ---")
        print(f"City prompt: {city_prompt_path}")
        print(f"Sector prompt: {sector_prompt_path}")

    @patch('agents.planner.OpenAI')
    def test_prompt_combination_display(self, MockOpenAI):
        """Test and display how prompts are combined."""
        # Mock the OpenAI responses so we don't make real API calls
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Mock response"))]
        MockOpenAI.return_value.chat.completions.create.return_value = mock_response
        
        # Test city+sector state
        city_sector_state = create_initial_state(city_name="Kraków", sector_name="stationary_energy")
        
        print(f"\n--- Testing City + Sector Prompt Combination ---")
        print(f"City: {city_sector_state.target_city}")
        print(f"Sector: {city_sector_state.target_sector}")
        print(f"Research Mode: {city_sector_state.research_mode}")
        
        # Load the actual prompts to show what would be combined
        city_prompt_path = Path(__file__).parent.parent / "agents" / "prompts" / "agent1_planner_city.md"
        sector_prompt_path = Path(__file__).parent.parent / "agents" / "prompts" / "stationary_energy.md"
        
        try:
            with open(city_prompt_path, 'r', encoding='utf-8') as f:
                city_prompt = f.read()
            
            with open(sector_prompt_path, 'r', encoding='utf-8') as f:
                sector_prompt = f.read()
            
            print(f"\n--- City Prompt (first 500 chars) ---")
            print(city_prompt[:500] + "...")
            
            print(f"\n--- Sector Enhancement (first 500 chars) ---")
            sector_enhancement = f"\n\n## SECTOR-SPECIFIC ENHANCEMENT FOR STATIONARY_ENERGY:\n"
            sector_enhancement += "Use the following sector-specific GHGI knowledge to enhance your city analysis:\n\n"
            sector_enhancement += sector_prompt[:500]
            sector_enhancement += "\n\n**Apply this sector knowledge to your city analysis, focusing on how these sector-specific requirements apply to city-level research.**"
            print(sector_enhancement)
            
            print(f"\n--- Combined Prompt Length ---")
            combined_length = len(city_prompt) + len(sector_enhancement)
            print(f"City prompt: {len(city_prompt)} chars")
            print(f"Sector enhancement: {len(sector_enhancement)} chars") 
            print(f"Combined total: {combined_length} chars")
            
        except FileNotFoundError as e:
            print(f"Prompt file not found: {e}")
            self.fail(f"Required prompt file not found: {e}")

    def test_city_sector_validation(self):
        """Test validation rules for city+sector combinations."""
        # Valid: City only
        state1 = create_initial_state(city_name="Warsaw")
        self.assertEqual(state1.research_mode, "city")
        self.assertIsNone(state1.target_sector)
        
        # Valid: City + Sector
        state2 = create_initial_state(city_name="Warsaw", sector_name="afolu")
        self.assertEqual(state2.research_mode, "city")
        self.assertEqual(state2.target_sector, "afolu")
        
        # Valid: Country + Sector
        state3 = create_initial_state(country_name="Poland", sector_name="afolu")
        self.assertEqual(state3.research_mode, "country")
        self.assertEqual(state3.target_sector, "afolu")
        
        # Invalid: City + Country
        with self.assertRaises(ValueError):
            create_initial_state(city_name="Warsaw", country_name="Poland")
        
        # Invalid: Country without sector
        with self.assertRaises(ValueError):
            create_initial_state(country_name="Poland")

    def print_cli_usage_examples(self):
        """Print usage examples for the new functionality."""
        print(f"\n--- CLI Usage Examples ---")
        print(f"City only:           python main.py --city 'Kraków'")
        print(f"City + Sector:       python main.py --city 'Kraków' --sector stationary_energy")
        print(f"City + English:      python main.py --city 'Kraków' --english")
        print(f"City + Sector + Eng: python main.py --city 'Kraków' --sector afolu --english")
        print(f"Country + Sector:    python main.py --country 'Poland' --sector stationary_energy")

if __name__ == "__main__":
    # Create a test instance and run the display methods
    test = TestCityPromptCombination()
    test.setUp()
    
    print("=" * 80)
    print("CITY + SECTOR FUNCTIONALITY DEMONSTRATION")
    print("=" * 80)
    
    try:
        test.test_city_only_state_creation()
        test.test_city_plus_sector_state_creation()
        test.test_prompt_loading_logic()
        test.test_prompt_combination_display()
        test.test_city_sector_validation()
        test.print_cli_usage_examples()
        
        print(f"\n" + "=" * 80)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        
    except Exception as e:
        print(f"Test failed: {e}")
        raise
    finally:
        test.tearDown()
    
    # Also run the unittest framework
    print(f"\n--- Running Unit Tests ---")
    unittest.main(verbosity=2) 