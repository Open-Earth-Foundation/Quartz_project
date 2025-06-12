import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import subprocess
import sys
import os
import json
import glob
import time # For managing file creation timings if needed
import shutil # For cleaning up runs directory
import tempfile # Added
import io # Added
import contextlib # Added
import argparse # Added
import asyncio # Added
from typing import Optional # Added to fix linter error
from pydantic import HttpUrl

# Adjust path to import from parent directory if necessary
# This assumes tests are run from the project root or this path is adjusted by pytest
from agent_state import AgentState, create_initial_state # For type hinting if needed
from agents.schemas import SearchPlanSchema, ReviewerLLMResponse, SearchQuery, SearchResultItem # For mock data creation
import config # To potentially override OUTPUT_DIR for tests

# Configure logging for tests - might be overwritten by CLI
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Adjust path to import from project root if test_cli.py is in a subfolder like 'tests'
# This assumes 'tests' is a subdir of the project root.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from main import main_async # Added

# Helper to create mock LLM JSON content (similar to test_graph_integration)
def create_mock_cli_llm_json(schema_type: str, country: str, action: str = "accept") -> str:
    if schema_type == "SearchPlanSchema":
        plan_data = SearchPlanSchema(
            search_queries=[
                SearchQuery(query=f"{country} CLI test query", language="en", priority="high", target_type="cli_test_report", rank=1)
            ],
            target_country_locode="XT", # Test LOCODE
            primary_languages=["English"],
            key_institutions=[f"Ministry of CLI Test {country}"],
            international_sources=["TestFCCC"],
            document_types=["JSON", "Report"],
            confidence="High",
            challenges=[]
        )
        return plan_data.model_dump_json()
    elif schema_type == "ReviewerLLMResponse":
        review_data = ReviewerLLMResponse(
            overall_assessment_notes=f"CLI Test Review. Action: {action}",
            relevance_score="High", relevance_reasoning="Relevant for CLI test.",
            credibility_score="High", credibility_reasoning="Mock source, credible for test.",
            completeness_score="High", completeness_reasoning="Complete for CLI test.",
            overall_confidence="High",
            suggested_action=action, # type: ignore
            action_reasoning=f"CLI test suggests {action}.",
            refinement_details="None for CLI test."
        )
        return review_data.model_dump_json()
    return "{}"

class TestCLI(unittest.TestCase):
    TEST_COUNTRY_NAME = "TestCLILand"
    TEST_SECTOR_NAME = "stationary_energy" # Define default sector for CLI tests
    TEST_OUTPUT_DIR = "temp_test_cli_runs" # Use different temp dir name

    def setUp(self):
        self.original_output_dir = config.OUTPUT_DIR
        config.OUTPUT_DIR = self.TEST_OUTPUT_DIR
        # Ensure the temp output directory is clean before each test
        if os.path.exists(self.TEST_OUTPUT_DIR):
            shutil.rmtree(self.TEST_OUTPUT_DIR)
        os.makedirs(self.TEST_OUTPUT_DIR, exist_ok=True)
        
        # Mock API keys to prevent real calls even if mocks fail
        self.original_openrouter_key = config.OPENROUTER_API_KEY
        self.original_firecrawl_key = config.FIRECRAWL_API_KEY
        config.OPENROUTER_API_KEY = "mock_cli_test_key"
        config.FIRECRAWL_API_KEY = "mock_cli_firecrawl_key"

    def tearDown(self):
        # Clean up the temporary output directory
        if os.path.exists(self.TEST_OUTPUT_DIR):
            shutil.rmtree(self.TEST_OUTPUT_DIR)
        config.OUTPUT_DIR = self.original_output_dir
        config.OPENROUTER_API_KEY = self.original_openrouter_key
        config.FIRECRAWL_API_KEY = self.original_firecrawl_key

    @patch('agents.reviewer.OpenAI')
    @patch('agents.utils.google_search_async')
    @patch('agents.planner.OpenAI')
    async def test_cli_run_produces_summary_and_json_output(self,
                                                       mock_planner_openai: MagicMock,
                                                       mock_researcher_google: AsyncMock, # Corrected type hint
                                                       mock_reviewer_openai: MagicMock):
        print("TEST_CLI: Starting test_cli_run_produces_summary_and_json_output (direct call)", flush=True)
        logger.info(f"Starting CLI test for country: {self.TEST_COUNTRY_NAME}, sector: {self.TEST_SECTOR_NAME} (direct call)")

        # --- Configure Mocks to ensure 'accept' outcome --- #
        print("TEST_CLI: Configuring planner mock", flush=True)
        mock_planner_openai_instance = mock_planner_openai.return_value.chat.completions
        mock_planner_markdown_resp = MagicMock()
        mock_planner_markdown_resp.choices = [MagicMock(message=MagicMock(content="## Mock CLI Planner Markdown Output\\n*   **Country LOCODE (if known):** XT"))]
        mock_planner_json_resp = MagicMock()
        # Assuming create_mock_cli_llm_json is a method or accessible helper
        mock_planner_json_resp.choices = [MagicMock(message=MagicMock(content=self.create_mock_cli_llm_json("SearchPlanSchema", self.TEST_COUNTRY_NAME)))]
        mock_planner_openai_instance.create.side_effect = [mock_planner_markdown_resp, mock_planner_json_resp]

        print("TEST_CLI: Configuring researcher mock", flush=True)
        mock_researcher_google.return_value = [
            SearchResultItem(url=HttpUrl("http://mockurl.cli/test"), title="Mock CLI Doc", content="mock content", score=0.9).model_dump()
        ]

        print("TEST_CLI: Configuring reviewer mock", flush=True)
        mock_reviewer_openai_instance = mock_reviewer_openai.return_value.chat.completions
        mock_reviewer_openai_instance.create.return_value = MagicMock(choices=[
            MagicMock(message=MagicMock(content=self.create_mock_cli_llm_json("ReviewerLLMResponse", self.TEST_COUNTRY_NAME, action="accept")))
        ])

        # --- Prepare arguments and environment for direct main_async call ---
        mock_args = argparse.Namespace(
            country=self.TEST_COUNTRY_NAME,
            sector=self.TEST_SECTOR_NAME,
            log_level="DEBUG",
            max_iterations=2
        )
        cli_config_overrides = {"MAX_ITERATIONS": mock_args.max_iterations}

        # Dummy API keys for os.environ to satisfy config loading/checks in main code
        # The actual API calls are mocked, so these keys won't be used for real calls.
        mock_env_vars = {
            "FIRECRAWL_API_KEY": "dummy-firecrawl-key-for-test",
            "OPENROUTER_API_KEY": "sk-dummy-openrouter-key-for-test",
            "LANGCHAIN_TRACING_V2": "false", # Ensure tracing is off for tests
            "LANGCHAIN_API_KEY": "dummy-lc-key"
        }

        stdout_capture = io.StringIO()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('config.OUTPUT_DIR', tmpdir):
                with contextlib.redirect_stdout(stdout_capture):
                    # Patch os.environ for the duration of this context
                    # clear=True ensures only our mock_env_vars are seen if config relies on os.environ at runtime
                    with patch.dict(os.environ, mock_env_vars, clear=True): 
                        # Reload config if it caches values from os.environ at import time
                        # This is advanced. For now, assume config.py uses os.getenv() on demand
                        # or that the initial import happens after this patch.dict is active, config values from previous env might persist.
                        # A more robust way for config is to patch config attributes directly if they don't change.
                        # However, the OpenAI/Firecrawl patches are the primary mechanism.
                        try:
                            await main_async(mock_args, cli_config_overrides)
                        except Exception as e:
                            logger.error(f"Error during main_async call: {e}", exc_info=True)
                            self.fail(f"main_async raised an unexpected exception: {e}")

            captured_output = stdout_capture.getvalue()
            logger.info(f"Captured stdout:\\n{captured_output}")

            # --- Assertions ---
            self.assertIn(f"Target Country:          {self.TEST_COUNTRY_NAME}", captured_output)
            self.assertIn(f"Target Sector:           {self.TEST_SECTOR_NAME}", captured_output)
            self.assertIn("Final Review Action:     accept", captured_output)
            self.assertIn("Structured Items Found:  1", captured_output) # Based on extractor_node_stub + researcher mock
            
            # Check for JSON file output
            saved_files = os.listdir(tmpdir)
            self.assertEqual(len(saved_files), 1, f"Expected one JSON file to be saved in {tmpdir}, found: {saved_files}")
            
            json_filepath = os.path.join(tmpdir, saved_files[0])
            with open(json_filepath, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            self.assertEqual(saved_data["target_country"], self.TEST_COUNTRY_NAME)
            self.assertEqual(saved_data["final_review_action"], "accept")
            self.assertTrue(len(saved_data["structured_data"]) >= 1, "Expected at least one structured data item in JSON")
            # Check one of the mock items if extractor_node_stub structure is predictable
            # For instance, if it uses the researcher mock data:
            # Or if the stub always produces a specific item as in main.py
            mock_item_name_from_stub = "Mock Extracted Data Item from Stub" # From main.py extractor_node_stub
            found_mock_item = any(item.get("name") == mock_item_name_from_stub for item in saved_data["structured_data"])
            self.assertTrue(found_mock_item, f"Did not find '{mock_item_name_from_stub}' in saved structured_data")

    # Make sure create_mock_cli_llm_json is defined or imported correctly
    # This is a simplified version, ensure it matches your actual helper
    def create_mock_cli_llm_json(self, schema_type: str, country_name: str, action: Optional[str] = None) -> str:
        if schema_type == "SearchPlanSchema":
            return json.dumps({
                "country_name": country_name,
                "country_locode": "XT", # Mock LOCODE
                "sectors_and_categories": [
                    {"sector": "Energy", "category": "Overall Emissions"}
                ]
            })
        elif schema_type == "ReviewerLLMResponse":
            return json.dumps({
                "decision": action or "accept",
                "reasoning": "Mock reasoning from CLI test.",
                "confidence_assessment": "High",
                "items_to_keep": [0], # Assuming at least one item passed by extractor
                "items_to_discard": [],
                "issues_identified": []
            })
        return "{}"

    @patch('main.run_agent', new_callable=AsyncMock)
    @patch('main.save_results_to_json')
    async def test_cli_run_produces_summary_and_json_output_with_sector(self,
                                                                 mock_run_agent: AsyncMock,
                                                                 mock_save_results: MagicMock):
        country_name = "Testland"
        sector_name = "stationary_energy" # Define sector for test

        # Mock subprocess.run (if used for direct CLI call simulation - not needed if calling main_async directly)
        # Ensure the command includes the new --sector argument
        with patch('main.run_agent', new_callable=AsyncMock) as mock_run_agent:
            # Setup mock return values
            mock_state = create_initial_state(country_name, sector_name) # Pass sector
            mock_state.metadata["next_step_after_review"] = "accept" # Simulate accept for saving
            mock_state.structured_data = [{"mock": "data"}] # Add dummy data
            mock_state.decision_log.append({"agent": "Test", "action": "mock_end"})
            mock_run_agent.return_value = mock_state
            mock_save_results.return_value = "mock_results.json"

            # Simulate running the CLI command by calling main_async directly
            # Create args Namespace including the sector
            mock_args = argparse.Namespace(
                country=country_name, 
                sector=sector_name, 
                log_level="INFO", 
                max_iterations=None
            )
            await main_async(mock_args)
            
            # Assert that run_agent was called with the correct country and sector
            mock_run_agent.assert_called_once_with(country_name, sector_name, None)
            # Assert that save was called because action was accept and data exists
            mock_save_results.assert_called_once()

    # Add other tests as needed

if __name__ == '__main__':
    # unittest.main() might have issues with async tests directly.
    # Recommended to run tests using pytest.
    print("Run tests using pytest") 