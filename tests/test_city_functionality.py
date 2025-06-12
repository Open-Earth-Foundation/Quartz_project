"""
Tests for city-based research functionality.
These tests verify that the agent can properly handle city-based queries,
use the city planner prompt, and generate appropriate search strategies.
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open, AsyncMock
import json
import os
import asyncio
import argparse
import tempfile
import io
import contextlib
from pathlib import Path
import pytest

# Import project modules
from agent_state import AgentState, create_initial_state
from agents.planner import planner_node
from agents.schemas import SearchPlanSchema, SearchQuery
from main import main_async, run_agent
import config

class TestCityFunctionality(unittest.TestCase):
    """Test suite for city-based research functionality."""

    def setUp(self):
        """Setup test environment."""
        self.test_city = "San Francisco"
        self.test_city_simple = "Warsaw"
        
        # Store original config values
        self.original_output_dir = config.OUTPUT_DIR
        self.original_openrouter_key = config.OPENROUTER_API_KEY
        self.original_firecrawl_key = config.FIRECRAWL_API_KEY
        
        # Set test config values
        config.OUTPUT_DIR = "temp_test_city_runs"
        config.OPENROUTER_API_KEY = "mock_city_test_key"
        config.FIRECRAWL_API_KEY = "mock_city_firecrawl_key"
        
        # Ensure test configs are available
        config.THINKING_MODEL = config.THINKING_MODEL or "test_model_city_think"
        config.STRUCTURED_MODEL = config.STRUCTURED_MODEL or "test_model_city_structured"
        config.OPENROUTER_BASE_URL = config.OPENROUTER_BASE_URL or "http://localhost:1234"

    def tearDown(self):
        """Clean up test environment."""
        # Restore original config values
        config.OUTPUT_DIR = self.original_output_dir
        config.OPENROUTER_API_KEY = self.original_openrouter_key
        config.FIRECRAWL_API_KEY = self.original_firecrawl_key

    def test_agent_state_creation_city_mode(self):
        """Test that AgentState is properly created for city mode."""
        # Test city-only mode
        state = create_initial_state(city_name=self.test_city)
        
        self.assertEqual(state.target_city, self.test_city)
        self.assertEqual(state.research_mode, "city")
        self.assertEqual(state.prompt, f"City: {self.test_city}")
        self.assertIsNone(state.target_country)
        self.assertIsNone(state.target_sector)
        
        # Check metadata
        self.assertEqual(state.metadata.get("research_mode"), "city")
        
        # Check decision log
        self.assertTrue(len(state.decision_log) > 0)
        init_log = state.decision_log[0]
        self.assertEqual(init_log.get("action"), "init")
        self.assertEqual(init_log.get("city"), self.test_city)
        self.assertEqual(init_log.get("research_mode"), "city")

    def test_agent_state_creation_city_plus_sector_mode(self):
        """Test that AgentState is properly created for city+sector mode."""
        # Test city+sector mode
        state = create_initial_state(city_name=self.test_city, sector_name="afolu")
        
        self.assertEqual(state.target_city, self.test_city)
        self.assertEqual(state.target_sector, "afolu")
        self.assertEqual(state.research_mode, "city")
        self.assertEqual(state.prompt, f"City: {self.test_city}, Sector: afolu")
        self.assertIsNone(state.target_country)
        
        # Check metadata
        self.assertEqual(state.metadata.get("research_mode"), "city")
        
        # Check decision log
        self.assertTrue(len(state.decision_log) > 0)
        init_log = state.decision_log[0]
        self.assertEqual(init_log.get("action"), "init")
        self.assertEqual(init_log.get("city"), self.test_city)
        self.assertEqual(init_log.get("sector"), "afolu")
        self.assertEqual(init_log.get("research_mode"), "city")

    def test_agent_state_creation_prevents_mixed_modes(self):
        """Test that AgentState creation prevents mixing city and country modes."""
        with self.assertRaises(ValueError) as context:
            create_initial_state(city_name=self.test_city, country_name="Poland", sector_name="afolu")
        
        self.assertIn("Cannot specify both city_name and country_name", str(context.exception))

    def test_agent_state_creation_requires_mode(self):
        """Test that AgentState creation requires either city or country/sector."""
        with self.assertRaises(ValueError) as context:
            create_initial_state()
        
        self.assertIn("Must specify either city_name OR both country_name and sector_name", str(context.exception))

    def test_city_sector_combinations(self):
        """Test various valid city/sector combinations."""
        # Valid: City only
        state1 = create_initial_state(city_name="Warsaw")
        self.assertEqual(state1.research_mode, "city")
        self.assertIsNone(state1.target_sector)
        self.assertEqual(state1.prompt, "City: Warsaw")
        
        # Valid: City + Sector combinations
        for sector in ['afolu', 'ippu', 'stationary_energy', 'transportation', 'waste']:
            state = create_initial_state(city_name="Warsaw", sector_name=sector)
            self.assertEqual(state.research_mode, "city")
            self.assertEqual(state.target_sector, sector)
            self.assertEqual(state.prompt, f"City: Warsaw, Sector: {sector}")

    def test_city_planner_prompt_exists(self):
        """Test that the city planner prompt file exists and has the correct placeholder."""
        prompt_path = Path(__file__).parent.parent / "agents" / "prompts" / "agent1_planner_city.md"
        
        self.assertTrue(prompt_path.exists(), f"City planner prompt file does not exist at {prompt_path}")
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn("{city_name_from_AgentState}", content, "City placeholder not found in prompt")
        self.assertIn("6 for the city itself and 9 for different administrative regions", content, "Expected query distribution not mentioned")
        self.assertIn("City Queries (6 total)", content, "City queries section not found")
        self.assertIn("Regional Queries Distribution (9 total)", content, "Regional queries section not found")

    @pytest.mark.asyncio
    @patch('os.makedirs')
    @patch('builtins.open')
    @patch('agents.planner.OpenAI')
    async def test_planner_uses_city_prompt_in_city_mode(self, MockOpenAI, mock_file_open, mock_makedirs):
        """Test that planner uses the city-specific prompt in city mode."""
        # Create city state
        city_state = create_initial_state(city_name=self.test_city)
        
        # Mock LLM responses
        mock_city_analysis = """
        # City Analysis for San Francisco
        
        ## 1. City Context & Basic Info:
        - **Identified City:** San Francisco
        - **Country:** United States
        - **Country LOCODE:** US
        - **Primary Language(s):** English
        
        ## 2. Administrative Structure Analysis:
        - **City Administrative Level:** City and County
        - **Regional Hierarchy:** State > County > City
        - **Region Names:** California (State), San Francisco County, City of San Francisco
        - **Administrative Complexity:** 2 meaningful levels above city
        
        ## 3. Search Query Strategy:
        ### City Queries (6 total):
        1. San Francisco GHG emissions inventory
        2. San Francisco Climate Action Plan
        3. San Francisco energy consumption data
        4. San Francisco waste management emissions
        5. San Francisco transportation emissions
        6. San Francisco urban sustainability reports
        
        ### Regional Queries Distribution (9 total):
        #### California State (5 queries):
        1. California state greenhouse gas inventory
        2. California energy statistics
        3. California transportation emissions
        4. California waste management data
        5. California climate policies
        
        #### San Francisco County (4 queries):
        1. San Francisco County emissions data
        2. Bay Area regional emissions
        3. San Francisco County energy data
        4. Regional waste processing data
        """
        
        mock_city_json = {
            "search_queries": [
                {"query": "San Francisco GHG emissions inventory", "language": "en", "priority": "high", "target_type": "city_emissions", "rank": 1},
                {"query": "San Francisco Climate Action Plan", "language": "en", "priority": "high", "target_type": "city_climate_plan", "rank": 2},
                {"query": "San Francisco energy consumption data", "language": "en", "priority": "high", "target_type": "city_energy", "rank": 3},
                {"query": "San Francisco waste management emissions", "language": "en", "priority": "medium", "target_type": "city_waste", "rank": 4},
                {"query": "San Francisco transportation emissions", "language": "en", "priority": "medium", "target_type": "city_transport", "rank": 5},
                {"query": "San Francisco urban sustainability reports", "language": "en", "priority": "medium", "target_type": "city_planning", "rank": 6},
                {"query": "California state greenhouse gas inventory", "language": "en", "priority": "high", "target_type": "state_emissions", "rank": 7},
                {"query": "California energy statistics", "language": "en", "priority": "medium", "target_type": "state_energy", "rank": 8},
                {"query": "California transportation emissions", "language": "en", "priority": "medium", "target_type": "state_transport", "rank": 9},
                {"query": "California waste management data", "language": "en", "priority": "medium", "target_type": "state_waste", "rank": 10},
                {"query": "California climate policies", "language": "en", "priority": "low", "target_type": "state_policy", "rank": 11},
                {"query": "San Francisco County emissions data", "language": "en", "priority": "medium", "target_type": "county_emissions", "rank": 12},
                {"query": "Bay Area regional emissions", "language": "en", "priority": "medium", "target_type": "regional_emissions", "rank": 13},
                {"query": "San Francisco County energy data", "language": "en", "priority": "low", "target_type": "county_energy", "rank": 14},
                {"query": "Regional waste processing data", "language": "en", "priority": "low", "target_type": "regional_waste", "rank": 15}
            ],
            "target_country_locode": "US",
            "primary_languages": ["English"],
            "key_institutions": ["San Francisco Department of Environment", "California Air Resources Board"],
            "international_sources": ["ICLEI", "C40 Cities"],
            "document_types": ["Climate Action Plans", "GHG Inventories", "Sustainability Reports"],
            "confidence": "High",
            "challenges": ["Data granularity at city level", "Regional data integration"]
        }
        
        # Configure mock responses
        mock_response_markdown = MagicMock()
        mock_response_markdown.choices = [MagicMock(message=MagicMock(content=mock_city_analysis))]
        mock_response_json = MagicMock()
        mock_response_json.choices = [MagicMock(message=MagicMock(content=json.dumps(mock_city_json)))]
        
        mock_openai_instance = MockOpenAI.return_value
        mock_openai_instance.chat.completions.create.side_effect = [mock_response_markdown, mock_response_json]
        
        # Mock file operations
        mock_handle_raw = mock_open().return_value
        mock_handle_structured = mock_open().return_value
        mock_file_open.side_effect = [mock_handle_raw, mock_handle_structured]
        
        # Run planner
        updated_state = await planner_node(city_state)
        
        # Verify the state is updated correctly
        self.assertEqual(updated_state.target_city, self.test_city)
        self.assertEqual(updated_state.research_mode, "city")
        self.assertEqual(len(updated_state.search_plan), 15, "Should have 15 search queries (6 city + 9 regional)")
        
        # Verify query distribution
        city_queries = [q for q in updated_state.search_plan if "San Francisco" in q["query"] and "County" not in q["query"] and "California" not in q["query"] and "Bay Area" not in q["query"]]
        state_queries = [q for q in updated_state.search_plan if "California" in q["query"]]
        county_queries = [q for q in updated_state.search_plan if any(term in q["query"] for term in ["County", "Bay Area", "Regional"])]
        
        self.assertEqual(len(city_queries), 6, f"Should have 6 city queries, got {len(city_queries)}")
        self.assertEqual(len(state_queries), 5, f"Should have 5 state queries, got {len(state_queries)}")
        self.assertEqual(len(county_queries), 4, f"Should have 4 county/regional queries, got {len(county_queries)}")
        
        # Verify queries are ranked
        ranks = [q["rank"] for q in updated_state.search_plan]
        self.assertEqual(ranks, sorted(ranks), "Queries should be sorted by rank")
        self.assertEqual(min(ranks), 1, "Ranks should start from 1")
        self.assertEqual(max(ranks), 15, "Ranks should go up to 15")
        
        # Verify file operations for city mode
        self.assertEqual(mock_file_open.call_count, 2, "Should save both raw and structured outputs")
        
        # Check that the structured file is saved with city prefix
        structured_call = mock_file_open.call_args_list[1]
        structured_filepath = structured_call.args[0]
        self.assertIn("city_San_Francisco", os.path.basename(structured_filepath), "Structured file should have city prefix")

    def create_mock_args(self, city=None, country=None, sector=None, english=False):
        """Helper to create mock CLI arguments."""
        args = argparse.Namespace()
        args.city = city
        args.country = country
        args.sector = sector
        args.english = english
        args.log_level = "DEBUG"
        args.max_iterations = 2
        return args

    @pytest.mark.asyncio
    @patch('main.ghgi_graph.ainvoke', new_callable=AsyncMock)
    async def test_run_agent_city_mode(self, mock_graph_invoke):
        """Test that run_agent works correctly in city mode."""
        # Mock the graph execution
        mock_final_state = {
            "target_city": self.test_city,
            "research_mode": "city",
            "target_country": None,
            "target_sector": None,
            "current_iteration": 1,
            "metadata": {"research_mode": "city"},
            "decision_log": [{"action": "init", "city": self.test_city}],
            "search_plan": [{"query": f"{self.test_city} emissions", "rank": 1}],
            "structured_data": [],
            "scraped_data": [],
            "urls": [],
            "confidence_scores": {},
            "start_time": "2024-01-01T00:00:00",
            "searches_conducted_count": 0,
            "consecutive_deep_dive_count": 0,
            "selected_for_extraction": [],
            "current_deep_dive_actions_count": 0,
            "target_country_locode": None,
            "iteration_count": 0,
            "prompt": f"City: {self.test_city}",
            "api_calls_succeeded": 0,
            "api_calls_failed": 0
        }
        mock_graph_invoke.return_value = mock_final_state
        
        # Run agent in city mode
        final_state = await run_agent(city_name=self.test_city)
        
        # Verify the state
        self.assertEqual(final_state.target_city, self.test_city)
        self.assertEqual(final_state.research_mode, "city")
        self.assertIsNone(final_state.target_country)
        self.assertIsNone(final_state.target_sector)
        
        # Verify graph was invoked with city state
        mock_graph_invoke.assert_called_once()
        call_args = mock_graph_invoke.call_args[0]
        initial_state = call_args[0]
        self.assertEqual(initial_state.target_city, self.test_city)
        self.assertEqual(initial_state.research_mode, "city")

    @pytest.mark.asyncio
    @patch('main.run_agent', new_callable=AsyncMock)
    async def test_main_async_city_mode(self, mock_run_agent):
        """Test that main_async correctly handles city mode."""
        # Mock the run_agent return
        mock_final_state = AgentState(
            prompt=f"City: {self.test_city}",
            target_city=self.test_city,
            research_mode="city",
            metadata={"research_mode": "city"},
            decision_log=[{"action": "init", "city": self.test_city}]
        )
        mock_run_agent.return_value = mock_final_state
        
        # Create city mode arguments
        args = self.create_mock_args(city=self.test_city)
        
        # Capture output
        stdout_capture = io.StringIO()
        with contextlib.redirect_stdout(stdout_capture):
            await main_async(args)
        
        captured_output = stdout_capture.getvalue()
        
        # Verify correct mode handling
        mock_run_agent.assert_called_once_with(
            city_name=self.test_city, 
            english_only_mode=False, 
            cli_config_overrides={}
        )
        
        # Verify output format
        self.assertIn(f"Target City:             {self.test_city}", captured_output)
        self.assertIn("Research Mode:           City-based", captured_output)

    def test_cli_argument_concepts(self):
        """Test CLI argument parsing concepts for city mode."""
        # Test that we understand city vs country mode distinction
        city_args = ["--city", "Warsaw"]
        country_args = ["--country", "Poland", "--sector", "afolu"]
        
        # Verify we can distinguish modes
        has_city = "--city" in city_args
        has_country_and_sector = "--country" in country_args and "--sector" in country_args
        
        self.assertTrue(has_city)
        self.assertTrue(has_country_and_sector)
        
        # Verify multi-word handling concept
        multiword_city = "San Francisco"
        self.assertIn(" ", multiword_city, "Multi-word cities contain spaces")

    @pytest.mark.asyncio
    @patch('agents.planner.OpenAI')
    async def test_planner_fallback_city_mode(self, MockOpenAI):
        """Test that planner provides fallback in city mode when LLM fails."""
        # Create city state
        city_state = create_initial_state(city_name=self.test_city_simple)
        
        # Mock LLM failure
        mock_openai_instance = MockOpenAI.return_value
        mock_openai_instance.chat.completions.create.side_effect = Exception("Simulated LLM failure")
        
        # Run planner
        updated_state = await planner_node(city_state)
        
        # Verify fallback behavior
        self.assertEqual(len(updated_state.search_plan), 1, "Should have one fallback query")
        fallback_query = updated_state.search_plan[0]
        self.assertIn(self.test_city_simple, fallback_query["query"], "Fallback query should contain city name")
        self.assertEqual(fallback_query["target_type"], "fallback_generic_city", "Should use city fallback type")

    def test_search_plan_schema_validates_city_queries(self):
        """Test that SearchPlanSchema correctly validates city-generated queries."""
        city_queries = [
            SearchQuery(
                query="Warsaw greenhouse gas emissions inventory",
                language="en",
                priority="high",
                target_type="city_emissions",
                rank=1
            ),
            SearchQuery(
                query="Mazowieckie voivodeship emissions data",
                language="pl",
                priority="medium",
                target_type="regional_emissions",
                rank=2
            )
        ]
        
        plan_schema = SearchPlanSchema(
            search_queries=city_queries,
            target_country_locode="PL",
            primary_languages=["Polish", "English"],
            key_institutions=["Warsaw City Hall", "Mazowieckie Marshal Office"],
            confidence="High"
        )
        
        # Verify schema validation passes
        self.assertEqual(len(plan_schema.search_queries), 2)
        self.assertEqual(plan_schema.target_country_locode, "PL")
        self.assertIn("Polish", plan_schema.primary_languages or [])

    def test_filename_generation_city_mode(self):
        """Test that result filenames are generated correctly for city mode."""
        from main import save_results_to_json
        
        # Create a mock city state with accepted results
        city_state = AgentState(
            prompt=f"City: {self.test_city}",
            target_city=self.test_city,
            research_mode="city",
            metadata={
                "research_mode": "city",
                "next_step_after_structured_review": "accept"
            },
            structured_data=[{"name": "Test data", "url": "http://test.com"}]
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result_file = save_results_to_json(city_state, tmpdir)
            
            self.assertIsNotNone(result_file, "Should save results for accepted city research")
            if result_file is not None:
                filename = os.path.basename(result_file)
                self.assertTrue(filename.startswith("results_city_San_Francisco"), 
                              f"Filename should start with city prefix, got: {filename}")
                self.assertTrue(filename.endswith(".json"), "Should be a JSON file")
                
                # Verify file contents
                with open(result_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                
                self.assertEqual(saved_data["research_mode"], "city")
                self.assertEqual(saved_data["target_city"], self.test_city)
                self.assertIsNone(saved_data["target_country"])
                self.assertIsNone(saved_data["target_sector"])

    @pytest.mark.asyncio
    async def test_end_to_end_city_workflow_mock(self):
        """Test the complete city workflow with mocked components."""
        with patch('agents.planner.OpenAI') as MockPlannerOpenAI, \
             patch('agents.utils.google_search_async', new_callable=AsyncMock) as mock_search, \
             patch('agents.reviewer.OpenAI') as MockReviewerOpenAI, \
             patch('main.ghgi_graph.ainvoke', new_callable=AsyncMock) as mock_graph:
            
            # Mock all the components
            mock_planner_response = MagicMock()
            mock_planner_response.choices = [MagicMock(message=MagicMock(content="Mock city analysis"))]
            MockPlannerOpenAI.return_value.chat.completions.create.return_value = mock_planner_response
            
            mock_search.return_value = [{"url": "http://example.com", "title": "Test", "content": "test"}]
            
            mock_reviewer_response = MagicMock()
            mock_reviewer_response.choices = [MagicMock(message=MagicMock(content='{"suggested_action": "accept"}'))]
            MockReviewerOpenAI.return_value.chat.completions.create.return_value = mock_reviewer_response
            
            # Mock the final graph state
            final_mock_state = {
                "target_city": self.test_city,
                "research_mode": "city",
                "metadata": {"research_mode": "city", "next_step_after_structured_review": "accept"},
                "structured_data": [{"name": "Mock city data", "url": "http://test.com"}],
                "current_iteration": 1,
                "decision_log": [],
                "search_plan": [],
                "scraped_data": [],
                "urls": [],
                "confidence_scores": {},
                "start_time": "2024-01-01T00:00:00",
                "searches_conducted_count": 1,
                "consecutive_deep_dive_count": 0,
                "selected_for_extraction": [],
                "current_deep_dive_actions_count": 0,
                "target_country": None,
                "target_sector": None,
                "target_country_locode": None,
                "iteration_count": 0,
                "prompt": f"City: {self.test_city}",
                "api_calls_succeeded": 1,
                "api_calls_failed": 0
            }
            mock_graph.return_value = final_mock_state
            
            # Run the workflow
            result = await run_agent(city_name=self.test_city)
            
            # Verify the workflow completed
            self.assertEqual(result.target_city, self.test_city)
            self.assertEqual(result.research_mode, "city")
            self.assertGreater(len(result.structured_data), 0)

    @pytest.mark.asyncio
    @patch('main.ghgi_graph.ainvoke', new_callable=AsyncMock)
    async def test_run_agent_city_plus_sector_mode(self, mock_graph_invoke):
        """Test that run_agent works correctly in city+sector mode."""
        # Mock the graph execution for city+sector mode
        mock_final_state = {
            "target_city": self.test_city,
            "target_sector": "stationary_energy",
            "research_mode": "city",
            "target_country": None,
            "current_iteration": 1,
            "metadata": {"research_mode": "city"},
            "decision_log": [{"action": "init", "city": self.test_city, "sector": "stationary_energy"}],
            "search_plan": [{"query": f"{self.test_city} stationary energy emissions", "rank": 1}],
            "structured_data": [],
            "scraped_data": [],
            "urls": [],
            "confidence_scores": {},
            "start_time": "2024-01-01T00:00:00",
            "searches_conducted_count": 0,
            "consecutive_deep_dive_count": 0,
            "selected_for_extraction": [],
            "current_deep_dive_actions_count": 0,
            "target_country_locode": None,
            "iteration_count": 0,
            "prompt": f"City: {self.test_city}, Sector: stationary_energy",
            "api_calls_succeeded": 0,
            "api_calls_failed": 0
        }
        mock_graph_invoke.return_value = mock_final_state
        
        # Run agent in city+sector mode
        final_state = await run_agent(city_name=self.test_city, sector_name="stationary_energy")
        
        # Verify the state
        self.assertEqual(final_state.target_city, self.test_city)
        self.assertEqual(final_state.target_sector, "stationary_energy")
        self.assertEqual(final_state.research_mode, "city")
        self.assertIsNone(final_state.target_country)
        
        # Verify graph was invoked with city+sector state
        mock_graph_invoke.assert_called_once()
        call_args = mock_graph_invoke.call_args[0]
        initial_state = call_args[0]
        self.assertEqual(initial_state.target_city, self.test_city)
        self.assertEqual(initial_state.target_sector, "stationary_energy")
        self.assertEqual(initial_state.research_mode, "city")


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2) 