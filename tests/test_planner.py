"""
Unit tests for the Planner Agent node.
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import logging
import json
import os

from agent_state import AgentState, create_initial_state
from agents.planner import planner_node
import config

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Example mock LLM output for a test country
MOCK_LLM_OUTPUT_TESTLANDIA = """
# Analysis Results

## 1. Country Context & Basic Info:
*   **Identified Country:** Testlandia
*   **Country LOCODE (if known):** TL
*   **Primary Language(s):** Testlish

## 2. Standard GHGI Focus for Country:
*   **Typical Key GHGI Sectors:** Energy, Imagination, AFOLU (Abstract Farming)
*   **Common Relevant Greenhouse Gases:** CO2, WishfulGas (WG)
*   **Default Time Period:** Last Tuesday

## 3. Typical Activity Data Examples:
*   Energy: Daydreams per capita
*   Imagination: Ideas generated per hour

## 4. Units and Metrics:
*   Activity: DPC (Daydreams Per Capita)
*   Emissions: Gg CO2e, Tonnes WG

## 5. Potential Data Sources & Document Types (Generic & Country-Specific Ideas):
*   **Key National Institutions (General Types):** Ministry of Ideas, National Bureau of Daydreams
*   **International Sources:** Intergovernmental Panel on Fantastical Climate Change (IPFCC)
*   **Common Document/Data Types:** Annual Dream Report, .thought, .concept

## 6. Keyword & Search Term Generation (for Target Country):
*   **Primary English Keywords:**
    *   "Testlandia GHG inventory"
    *   "Testlandia daydream statistics"
    *   "Ministry of Ideas emissions report Testlandia"
*   **Primary Local Language Keywords (Optional but Recommended):**
    *   (Testlish) "Testlandia Treibhousgasinventar"
    *   (Testlish) "Testlandia Togdromstatistik"
*   **Secondary/Broader Keywords (Optional):**
    *   "climate change Testlandia"

## 7. Initial Confidence & Challenges Assessment:**
*   **Data Availability Confidence (General):** Medium
*   **Potential Challenges:** Data is often too abstract.
"""

# Mock JSON output for the second LLM call (structured data extraction)
# **Important**: Added "rank" field to each search_query
# Ranks are assigned sequentially for this mock.
MOCK_STRUCTURED_JSON_OUTPUT_TESTLANDIA = """
{
  "target_country_locode": "TL",
  "primary_languages": ["Testlish"],
  "key_institutions": ["Ministry of Ideas", "National Bureau of Daydreams"],
  "international_sources": ["Intergovernmental Panel on Fantastical Climate Change (IPFCC)"],
  "document_types": ["Annual Dream Report", ".thought", ".concept"],
  "search_queries": [
    {"query": "Testlandia GHG inventory", "language": "en", "priority": "high", "target_type": "national_report", "rank": 1},
    {"query": "Ministry of Ideas emissions report Testlandia", "language": "en", "priority": "high", "target_type": "specific_institution_report", "rank": 2},
    {"query": "(Testlish) \\\"Testlandia Treibhousgasinventar\\\"", "language": "testlish", "priority": "high", "target_type": "national_report_local_language", "rank": 3},
    {"query": "Testlandia daydream statistics", "language": "en", "priority": "medium", "target_type": "statistical_data", "rank": 4},
    {"query": "(Testlish) \\\"Testlandia Togdromstatistik\\\"", "language": "testlish", "priority": "medium", "target_type": "statistical_data_local_language", "rank": 5},
    {"query": "climate change Testlandia", "language": "en", "priority": "low", "target_type": "background_context", "rank": 6}
  ],
  "confidence": "Medium",
  "challenges": ["Data is often too abstract."]
}
"""

class TestPlannerNode(unittest.TestCase):

    def setUp(self):
        """Setup common test variables."""
        self.test_country = "Testlandia"
        self.test_sector = "stationary_energy"
        self.initial_state = create_initial_state(country_name=self.test_country, sector_name=self.test_sector)
        # Ensure critical configs are set for the test, even if defaults
        config.OPENROUTER_API_KEY = config.OPENROUTER_API_KEY or "test_key_if_not_set"
        config.THINKING_MODEL = config.THINKING_MODEL or "test_model_planner_think"
        config.STRUCTURED_MODEL = config.STRUCTURED_MODEL or "test_model_planner_structured"
        config.OPENROUTER_BASE_URL = config.OPENROUTER_BASE_URL or "http://localhost:1234"
        config.RESEARCH_OUTPUT_DIR = "mock_research_outputs"

    @patch('os.makedirs')
    @patch('builtins.open')
    @patch('agents.planner.OpenAI')
    async def test_planner_node_generates_plan_and_saves_output(self, MockOpenAI, mock_open_custom: MagicMock, mock_makedirs: MagicMock):
        """
        Test that planner_node correctly processes a country name,
        mocks LLM calls, generates a ranked/sorted search plan, and saves structured output.
        """
        # Configure distinct mock file handles for raw and structured outputs
        mock_handle_raw = mock_open().return_value # This provides a MagicMock pre-configured for file operations
        mock_handle_structured = mock_open().return_value
        
        # Make builtins.open return these handles in sequence for the two expected calls
        mock_open_custom.side_effect = [mock_handle_raw, mock_handle_structured]

        # Configure LLM mocks
        mock_response_markdown = MagicMock()
        mock_response_markdown.choices = [MagicMock(message=MagicMock(content=MOCK_LLM_OUTPUT_TESTLANDIA))]
        mock_response_json = MagicMock()
        mock_response_json.choices = [MagicMock(message=MagicMock(content=MOCK_STRUCTURED_JSON_OUTPUT_TESTLANDIA))]
        mock_openai_instance = MockOpenAI.return_value
        mock_openai_instance.chat.completions.create.side_effect = [mock_response_markdown, mock_response_json]

        logger.info(f"Testing planner_node for country: {self.test_country}")
        updated_state = await planner_node(self.initial_state)

        # Basic state assertions
        self.assertIsInstance(updated_state, AgentState)
        self.assertEqual(updated_state.target_country, self.test_country)
        self.assertTrue(len(updated_state.search_plan) > 0, "Search plan should not be empty.")
        # Rank assertions
        ranks = [item["rank"] for item in updated_state.search_plan if "rank" in item]
        self.assertEqual(ranks, sorted(ranks), "Search plan is not sorted by rank.")

        # Verify directory creation
        self.assertTrue(mock_makedirs.called, "os.makedirs was not called.")
        # Could be more specific: mock_makedirs.assert_any_call(os.path.normpath("logs/planner_outputs"), exist_ok=True)
        
        # Verify calls to open()
        self.assertEqual(mock_open_custom.call_count, 2, f"Expected 'open' to be called twice for raw and structured files. Got {mock_open_custom.call_count} calls. Call args: {mock_open_custom.call_args_list}")

        # ---- Verify structured JSON output file ----
        # The second call to open() should be for the structured file
        structured_open_call = mock_open_custom.call_args_list[1]
        structured_filepath_opened = structured_open_call.args[0]
        
        expected_dir_part = os.path.normpath("logs/planner_outputs")
        expected_filename_prefix = f"structured_output_{self.test_country}_{self.test_sector}_"

        self.assertTrue(os.path.basename(structured_filepath_opened).startswith(expected_filename_prefix),
                        f"Structured file basename '{os.path.basename(structured_filepath_opened)}' does not start with '{expected_filename_prefix}'.")
        self.assertTrue(os.path.dirname(structured_filepath_opened).endswith(expected_dir_part),
                        f"Structured file directory '{os.path.dirname(structured_filepath_opened)}' does not end with '{expected_dir_part}'.")

        # Check content written to mock_handle_structured
        # In planner.py, it writes: json.dump(json.loads(structured_output_str), f, indent=4) or parsed_plan_data.model_dump()
        # MOCK_STRUCTURED_JSON_OUTPUT_TESTLANDIA is the raw string from LLM mock.
        mock_handle_structured.write.assert_called()
        written_parts_structured = [args[0] for args, kwargs in mock_handle_structured.write.call_args_list]
        actual_written_content_structured = "".join(written_parts_structured)

        try:
            expected_obj = json.loads(MOCK_STRUCTURED_JSON_OUTPUT_TESTLANDIA)
            actual_obj = json.loads(actual_written_content_structured)
            self.assertEqual(actual_obj, expected_obj, "The JSON content written to structured file does not match expected.")
        except json.JSONDecodeError as e:
            self.fail(f"Failed to decode structured written content as JSON: {e}. Content: {actual_written_content_structured}")

        # ---- Optionally, verify raw markdown output file ----
        raw_open_call = mock_open_custom.call_args_list[0]
        raw_filepath_opened = raw_open_call.args[0]
        self.assertTrue(os.path.basename(raw_filepath_opened).startswith(f"planner_output_raw_{self.test_country}_"))
        mock_handle_raw.write.assert_any_call(MOCK_LLM_OUTPUT_TESTLANDIA)

        # Metadata and decision log checks (simplified examples)
        self.assertEqual(updated_state.target_country_locode, "TL")
        self.assertIn("Testlish", updated_state.metadata.get("primary_languages", []))
        self.assertTrue(any(log.get("agent") == "Planner" and log.get("action") == "plan_generated" for log in updated_state.decision_log))
        logger.info(f"Test for planner_node for {self.test_country} completed successfully.")

    @patch('os.makedirs')
    @patch('builtins.open')
    @patch('agents.planner.OpenAI')
    async def test_planner_node_handles_llm_failure_gracefully(self, MockOpenAI, mock_file_open, mock_makedirs):
        mock_openai_instance = MockOpenAI.return_value
        mock_openai_instance.chat.completions.create.side_effect = Exception("Simulated LLM API Failure")

        logger.info(f"Testing planner_node LLM failure for country: {self.test_country}")
        updated_state = await planner_node(self.initial_state)

        self.assertIsInstance(updated_state, AgentState)
        self.assertEqual(len(updated_state.search_plan), 1, "Search plan should have one entry on LLM failure.")
        
        plan_item_on_failure = updated_state.search_plan[0]
        self.assertIsInstance(plan_item_on_failure, dict, "Plan item on failure should be a dict.")
        
        # Verify the structure of the fallback search query item
        self.assertIn("query", plan_item_on_failure, "'query' key missing in fallback plan item.")
        self.assertTrue(self.test_country in plan_item_on_failure["query"], "Country name missing in fallback query.")
        self.assertIn("language", plan_item_on_failure, "'language' key missing in fallback plan item.")
        self.assertEqual(plan_item_on_failure["language"], "en")
        self.assertIn("priority", plan_item_on_failure, "'priority' key missing in fallback plan item.")
        self.assertEqual(plan_item_on_failure["priority"], "high")
        self.assertIn("target_type", plan_item_on_failure, "'target_type' key missing in fallback plan item.")
        self.assertEqual(plan_item_on_failure["target_type"], "exception_fallback")
        # Check that it does NOT have keys it shouldn't, like search_queries
        self.assertNotIn("search_queries", plan_item_on_failure, "'search_queries' key should not be in a single fallback plan item.")

        # Check for a decision log entry indicating failure
        failure_logged = any(
            log.get("agent") == "Planner" and "fail" in log.get("action", "").lower()
            for log in updated_state.decision_log
        )
        self.assertTrue(failure_logged, "Planner LLM failure was not logged.")
        mock_makedirs.assert_not_called() # Should not attempt to save if planning fails early
        mock_file_open.assert_not_called()

if __name__ == '__main__':
    unittest.main() 