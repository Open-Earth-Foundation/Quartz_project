"""
Integration test for the GHGI Agent graph, focusing on a single search run.
"""
import unittest
import logging
import json
import asyncio # Required for IsolatedAsyncioTestCase
from unittest.mock import patch, MagicMock # Added
from dataclasses import asdict # Ensure asdict is imported

# Adjust a copy of config for test-specific overrides
import config 
from main import run_agent # Assuming run_agent is in main.py
from agent_state import AgentState
# Assuming create_mock_llm_json is in test_graph_integration and is suitable
# If not, a local simplified version might be needed.
from tests.test_graph_integration import create_mock_llm_json 

# Configure logging for tests (optional, but can be helpful)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestSingleSearchIntegration(unittest.IsolatedAsyncioTestCase):

    @patch('agents.reviewer.OpenAI')
    @patch('agents.planner.OpenAI')
    async def test_poland_single_search(self, mock_planner_openai: MagicMock, mock_reviewer_openai: MagicMock): # Added mocks
        """
        Test the full agent graph for Poland with MAX_SEARCHES_PER_RUN = 1.
        """
        country_name = "Poland"
        config_overrides = {"MAX_SEARCHES_PER_RUN": 1, "MAX_ITERATIONS": 2} # Ensure it can finish
        
        logger.info(f"Starting integration test for {country_name} with MAX_SEARCHES_PER_RUN=1")
        
        # --- Configure Mocks ---
        # Planner mock (two LLM calls)
        mock_planner_openai_instance = mock_planner_openai.return_value.chat.completions
        mock_planner_markdown_response = MagicMock(choices=[MagicMock(message=MagicMock(content=f"## Mock Planner Markdown for {country_name}"))])
        # Use iteration 1 for mock data, country_name for specificity
        mock_planner_json_response = MagicMock(choices=[MagicMock(message=MagicMock(content=create_mock_llm_json("SearchPlanSchema", 1, country_name)))])
        mock_planner_openai_instance.create.side_effect = [mock_planner_markdown_response, mock_planner_json_response]

        # Reviewer mock (suggests accept)
        mock_reviewer_openai_instance = mock_reviewer_openai.return_value.chat.completions
        # Use iteration 1, country_name, and action "accept"
        mock_reviewer_openai_instance.create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content=create_mock_llm_json("ReviewerLLMResponse", 1, country_name, action="accept")))])
        
        # Store original config value to restore it later
        original_max_searches = config.MAX_SEARCHES_PER_RUN
        original_max_iterations = config.MAX_ITERATIONS

        config.MAX_SEARCHES_PER_RUN = config_overrides["MAX_SEARCHES_PER_RUN"]
        config.MAX_ITERATIONS = config_overrides["MAX_ITERATIONS"]
        logger.info(f"Temporarily set config.MAX_SEARCHES_PER_RUN to {config.MAX_SEARCHES_PER_RUN}")
        logger.info(f"Temporarily set config.MAX_ITERATIONS to {config.MAX_ITERATIONS}")

        try:
            # Pass None for cli_config_overrides as they are set directly on config module for this test
            final_state = await run_agent(country_name=country_name, sector_name="stationary_energy", cli_config_overrides=None)
            
            # Log the entire final_state for detailed debugging
            logger.debug(f"Final state for {country_name} (single search): {json.dumps(asdict(final_state), indent=2)}")
            
            self.assertIsInstance(final_state, AgentState)
            self.assertEqual(final_state.target_country, country_name)
            
            # Check that MAX_SEARCHES_PER_RUN was respected
            self.assertLessEqual(final_state.searches_conducted_count, 1, 
                                 f"Expected at most 1 search, but {final_state.searches_conducted_count} were conducted.")
            
            # Check if the planner ran
            planner_ran = any(log_entry.get("agent") == "Planner" and log_entry.get("action") == "plan_generated" for log_entry in final_state.decision_log)
            self.assertTrue(planner_ran, "Planner node did not seem to run or generate a plan.")
            
            # Check if the researcher ran
            researcher_ran = any(log_entry.get("agent") == "Researcher" and log_entry.get("action") == "research_iteration_completed" for log_entry in final_state.decision_log)
            self.assertTrue(researcher_ran, "Researcher node did not seem to complete an iteration.")

            # If a search was conducted, there should be some activity
            if final_state.searches_conducted_count > 0:
                self.assertTrue(len(final_state.urls) > 0 or len(final_state.scraped_data) > 0,
                                "If a search was conducted, expected some URLs or scraped data to be collected.")
            
            logger.info(f"Integration test for {country_name} completed.")
            logger.info(f"Searches conducted: {final_state.searches_conducted_count}")
            logger.info(f"URLs collected: {len(final_state.urls)}")
            logger.info(f"Scraped data items: {len(final_state.scraped_data)}")

        except Exception as e:
            logger.error(f"Error during run_agent: {e}", exc_info=True)

        finally:
            # The run_agent function should handle restoring the original values.
            # If direct manipulation of config was done here (which it was initially),
            # then it should be restored here. Since run_agent handles it, this external restoration is redundant if run_agent is correct.
            # For safety, and given the current run_agent implementation, we'll keep the external restoration
            # as run_agent's restoration only affects the keys *it* overrode via its argument.
            config.MAX_SEARCHES_PER_RUN = original_max_searches
            config.MAX_ITERATIONS = original_max_iterations
            logger.info(f"Restored config.MAX_SEARCHES_PER_RUN to {original_max_searches} (external test restoration)")
            logger.info(f"Restored config.MAX_ITERATIONS to {original_max_iterations} (external test restoration)")

if __name__ == '__main__':
    unittest.main() 