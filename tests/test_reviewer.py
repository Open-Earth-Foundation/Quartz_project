import unittest
from unittest.mock import patch, MagicMock
import json
import logging
from datetime import datetime

from agent_state import AgentState, create_initial_state
from agents.reviewer import reviewer_node as raw_content_reviewer_node
from agents.reviewer import structured_data_reviewer_node
from agents.schemas import ReviewerLLMResponse, RawReviewerLLMResponse, StructuredDataItem
import config # For setting API keys and models during test if necessary

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Helper for RawReviewerLLMResponse
def create_mock_raw_llm_response_content(
    suggested_next_action: str,
    documents_to_extract: list = None,
    overall_assessment: str = "Test raw assessment.",
    action_reasoning: str = "Raw action reason."
) -> str:
    if documents_to_extract is None:
        documents_to_extract = ["http://example.com/raw_doc1.html"] if suggested_next_action == "proceed_to_extraction" else []
    
    response_data = RawReviewerLLMResponse(
        overall_assessment=overall_assessment,
        documents_to_extract=documents_to_extract,
        suggested_next_action=suggested_next_action,
        action_reasoning=action_reasoning
    )
    return response_data.model_dump_json()

def create_mock_structured_llm_response_content(
    suggested_action: str,
    overall_notes: str = "Test structured assessment.",
    relevance: str = "High", rel_reason: str = "Structurally Relevant.",
    credibility: str = "High", cred_reason: str = "Structurally Credible.",
    completeness: str = "High", comp_reason: str = "Structurally Complete.",
    confidence: str = "High",
    action_reason: str = "Structured action reason."
) -> str:
    response_data = ReviewerLLMResponse(
        overall_assessment_notes=overall_notes,
        relevance_score=relevance, # type: ignore
        relevance_reasoning=rel_reason,
        credibility_score=credibility, # type: ignore
        credibility_reasoning=cred_reason,
        completeness_score=completeness, # type: ignore
        completeness_reasoning=comp_reason,
        overall_confidence=confidence, # type: ignore
        suggested_action=suggested_action, # type: ignore
        action_reasoning=action_reason,
        refinement_details="Test refinement details for deep dive" if suggested_action == "deep_dive" else None
    )
    return response_data.model_dump_json()

class TestRawContentReviewerNode(unittest.TestCase):

    def setUp(self):
        self.test_country = "RawTestlandia"
        self.test_sector = "raw_sector"
        self.initial_state = create_initial_state(country_name=self.test_country, sector_name=self.test_sector)
        
        # Setup for raw content reviewer: needs scraped_data
        self.initial_state.scraped_data = [
            {"url": "http://example.com/raw_doc1.html", "content": "Raw content page 1 for testing.", "markdown": "# Page 1"},
            {"url": "http://example.com/raw_doc2.pdf", "content": "PDF content raw text.", "markdown": "PDF Text"}
        ]
        self.initial_state.structured_data = [] # Should not be used by raw reviewer
        self.initial_state.search_plan = [
            {"query": "RawTestlandia raw sector data", "priority": "high"}
        ]
        self.initial_state.target_country_locode = "RT"

        config.OPENROUTER_API_KEY = config.OPENROUTER_API_KEY or "test_api_key_raw_reviewer"
        config.NORMAL_MODEL = config.NORMAL_MODEL or "test_model_for_raw_reviewer"
        config.OPENROUTER_BASE_URL = config.OPENROUTER_BASE_URL or "http://localhost:1234/v1"

    @patch('agents.reviewer.OpenAI') # Patching where OpenAI is instantiated in agents.reviewer
    def run_test_for_raw_action(self, mock_openai_client: MagicMock, suggested_next_action: str, expect_docs_extracted: bool = False, docs_to_extract_override: list = None):
        """Helper function to run a test case for a specific raw reviewer suggested action."""
        
        # Determine the expected final action based on fallback logic
        expected_final_action = suggested_next_action
        if suggested_next_action == "proceed_to_extraction" and not expect_docs_extracted and (docs_to_extract_override is None or not docs_to_extract_override):
            expected_final_action = "refine_plan"

        mock_llm_response_content = create_mock_raw_llm_response_content(
            suggested_next_action=suggested_next_action, # LLM is still told the original action
            documents_to_extract=docs_to_extract_override if docs_to_extract_override is not None else (["http://example.com/raw_doc1.html"] if expect_docs_extracted else [])
        )
        
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message = MagicMock()
        mock_completion.choices[0].message.content = mock_llm_response_content
        
        mock_client_instance = mock_openai_client.return_value
        mock_client_instance.chat.completions.create.return_value = mock_completion

        logger.info(f"Testing raw_content_reviewer_node with suggested_next_action: {suggested_next_action}, expecting final: {expected_final_action}")
        updated_state = raw_content_reviewer_node(self.initial_state) 

        self.assertIsInstance(updated_state, AgentState)
        self.assertEqual(updated_state.target_country, self.test_country)
        self.assertIn("last_raw_review_details", updated_state.metadata)
        
        # Assert against the expected_final_action
        self.assertEqual(updated_state.metadata["last_raw_review_details"]["suggested_next_action"], expected_final_action)
        self.assertEqual(updated_state.metadata.get("next_step_after_review"), expected_final_action)

        if expect_docs_extracted:
            self.assertTrue(len(updated_state.selected_for_extraction) > 0)
            if docs_to_extract_override:
                 self.assertEqual(sorted(updated_state.selected_for_extraction), sorted(docs_to_extract_override))
            else:
                 self.assertIn("http://example.com/raw_doc1.html", updated_state.selected_for_extraction)
        else:
            # This specific check for "proceed_to_extraction" without docs is now handled by expected_final_action
            # if suggested_next_action == "proceed_to_extraction":
            #      self.assertEqual(updated_state.metadata.get("next_step_after_review"), "refine_plan")
            #      self.assertEqual(updated_state.metadata["last_raw_review_details"]["suggested_next_action"], "refine_plan")
            self.assertTrue(len(updated_state.selected_for_extraction) == 0)
        
        self.assertTrue(len(updated_state.decision_log) > 0)
        last_log_entry = updated_state.decision_log[-1]
        self.assertEqual(last_log_entry["agent"], "Reviewer")
        # The decision log should also reflect the final action
        self.assertEqual(last_log_entry["suggested_action"], expected_final_action)
        # if suggested_next_action == "proceed_to_extraction" and not expect_docs_extracted and not docs_to_extract_override:
        #      self.assertEqual(last_log_entry["suggested_action"], "refine_plan")
        # else:
        #     self.assertEqual(last_log_entry["suggested_action"], suggested_next_action)

    def test_raw_reviewer_action_proceed(self):
        self.run_test_for_raw_action(suggested_next_action="proceed_to_extraction", expect_docs_extracted=True)

    def test_raw_reviewer_action_proceed_no_selection_fallback(self):
        self.run_test_for_raw_action(suggested_next_action="proceed_to_extraction", expect_docs_extracted=False, docs_to_extract_override=[])

    def test_raw_reviewer_action_refine_plan(self):
        self.run_test_for_raw_action(suggested_next_action="refine_plan", expect_docs_extracted=False)

    def test_raw_reviewer_action_end(self):
        self.run_test_for_raw_action(suggested_next_action="end", expect_docs_extracted=False)

    @patch('agents.reviewer.OpenAI')
    def test_raw_reviewer_no_scraped_data(self, mock_openai_client: MagicMock):
        self.initial_state.scraped_data = []
        logger.info("Testing raw_content_reviewer_node with no scraped data.")
        updated_state = raw_content_reviewer_node(self.initial_state)
        
        self.assertEqual(updated_state.metadata.get("next_step_after_review"), "end")
        last_log_entry = updated_state.decision_log[-1]
        self.assertEqual(last_log_entry["agent"], "Reviewer") 
        self.assertEqual(last_log_entry["action"], "skip_no_scraped_data") 
        mock_openai_client.chat.completions.create.assert_not_called()

    @patch('agents.reviewer.load_raw_reviewer_prompt_template')
    @patch('agents.reviewer.OpenAI') 
    def test_raw_reviewer_prompt_load_failure(self, mock_openai_client: MagicMock, mock_load_prompt: MagicMock):
        mock_load_prompt.return_value = "" 
        logger.info("Testing raw_content_reviewer_node with prompt load failure.")
        updated_state = raw_content_reviewer_node(self.initial_state)
        
        self.assertEqual(updated_state.metadata.get("next_step_after_review"), "end") 
        last_log_entry = updated_state.decision_log[-1]
        self.assertEqual(last_log_entry["agent"], "Reviewer") 
        self.assertEqual(last_log_entry["action"], "error_raw_review") 
        self.assertEqual(last_log_entry["message"], "Failed to load raw reviewer prompt template.")
        mock_openai_client.chat.completions.create.assert_not_called()

class TestStructuredDataReviewerNode(unittest.TestCase):

    def setUp(self):
        self.test_country = "Testlandia"
        self.test_sector = "stationary_energy"
        self.initial_state = create_initial_state(country_name=self.test_country, sector_name=self.test_sector)
        
        mock_structured_item = StructuredDataItem(
            name="Test Data Item Structured", url="http://example.com/structured.csv", method_of_access="download",
            sector="Waste", subsector="Solid Waste", data_format="CSV",
            description="Mock structured data for testing structured reviewer.",
            granularity="Regional", country=self.test_country, country_locode="TL",
            year=[2022], status="extracted"
        )
        self.initial_state.structured_data = [mock_structured_item.model_dump()] 
        self.initial_state.scraped_data = [ # Keep some scraped_data for context if prompt needs it
            {"url": "http://example.com/source1.html", "content": "Some raw content from source1", "markdown": "## Markdown from source1"}
        ]
        self.initial_state.search_plan = [
            {"query": "Testlandia waste data", "priority": "medium", "target_type": "official_report"}
        ]
        self.initial_state.target_country_locode = "TL"

        config.OPENROUTER_API_KEY = config.OPENROUTER_API_KEY or "test_api_key_structured_reviewer"
        # Structured reviewer might use THINKING_MODEL
        config.THINKING_MODEL = config.THINKING_MODEL or "test_model_for_structured_reviewer" 
        config.OPENROUTER_BASE_URL = config.OPENROUTER_BASE_URL or "http://localhost:1234/v1"
        # Ensure the prompt file path for structured reviewer is used by the node
        # The node itself loads this, so we just need to ensure the file exists for a real run
        # For mocks, we mock the LLM call directly.

    @patch('agents.reviewer.OpenAI') # Patching where OpenAI is instantiated in agents.reviewer
    def run_test_for_structured_action(self, mock_openai_client: MagicMock, suggested_action: str, refinement_details_expected: bool = False):
        mock_llm_response_content = create_mock_structured_llm_response_content(
            suggested_action=suggested_action
        )
        
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message = MagicMock()
        mock_completion.choices[0].message.content = mock_llm_response_content
        
        mock_client_instance = mock_openai_client.return_value
        mock_client_instance.chat.completions.create.return_value = mock_completion

        logger.info(f"Testing structured_data_reviewer_node with suggested_action: {suggested_action}")
        updated_state = structured_data_reviewer_node(self.initial_state) 

        self.assertIsInstance(updated_state, AgentState)
        self.assertEqual(updated_state.target_country, self.test_country)
        self.assertIn("last_structured_review_details", updated_state.metadata)
        self.assertEqual(updated_state.metadata["last_structured_review_details"]["suggested_action"], suggested_action)
        self.assertEqual(updated_state.metadata.get("next_step_after_structured_review"), suggested_action)

        if refinement_details_expected:
            self.assertIn("refinement_details", updated_state.metadata)
            self.assertIsNotNone(updated_state.metadata["refinement_details"])
            if suggested_action == "deep_dive":
                 self.assertEqual(updated_state.metadata["refinement_details"], "Test refinement details for deep dive")
        else:
            if "refinement_details" in updated_state.metadata:
                 self.assertNotEqual(updated_state.metadata["refinement_details"], "Test refinement details for deep dive")

        self.assertTrue(len(updated_state.decision_log) > 0)
        last_log_entry = updated_state.decision_log[-1]
        self.assertEqual(last_log_entry["agent"], "StructuredReviewer")
        self.assertEqual(last_log_entry["action"], "structured_review_completed")
        self.assertEqual(last_log_entry["suggested_action"], suggested_action)

    def test_structured_reviewer_action_accept(self):
        self.run_test_for_structured_action(suggested_action="accept")

    def test_structured_reviewer_action_reject(self):
        self.run_test_for_structured_action(suggested_action="reject")

    def test_structured_reviewer_action_deep_dive(self):
        self.run_test_for_structured_action(suggested_action="deep_dive", refinement_details_expected=True)

    @patch('agents.reviewer.OpenAI')
    def test_structured_reviewer_no_structured_data(self, mock_openai_client: MagicMock):
        self.initial_state.structured_data = []
        logger.info("Testing structured_data_reviewer_node with no structured data.")
        updated_state = structured_data_reviewer_node(self.initial_state)
        
        self.assertEqual(updated_state.metadata.get("next_step_after_structured_review"), "reject")
        last_log_entry = updated_state.decision_log[-1]
        self.assertEqual(last_log_entry["agent"], "StructuredReviewer")
        self.assertEqual(last_log_entry["action"], "skip_no_structured_data")
        mock_openai_client.chat.completions.create.assert_not_called()

    def test_structured_reviewer_final_decision_after_deep_dive(self):
        """Test that reviewer must make final decision (accept/reject) after one deep dive."""
        # Use a copy of the initial state but set consecutive_deep_dive_count to 1
        state = create_initial_state(country_name=self.test_country, sector_name=self.test_sector)
        state.structured_data = self.initial_state.structured_data.copy()
        state.search_plan = self.initial_state.search_plan.copy()
        state.target_country_locode = "TL"
        state.consecutive_deep_dive_count = 1  # One deep dive already performed
        
        # Mock OpenAI client to simulate LLM trying to suggest deep_dive
        with patch('agents.reviewer.OpenAI') as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            
            # Mock response that tries to suggest deep_dive (which should be overridden)
            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps({
                "overall_assessment_notes": "Need more investigation",
                "URL": "http://example.com",
                "subsector": "electricity",
                "relevance_score": "Medium",
                "relevance_reasoning": "Some relevant data found",
                "credibility_score": "Medium", 
                "credibility_reasoning": "Government source",
                "completeness_score": "Low",
                "completeness_reasoning": "Missing details",
                "overall_confidence": "Medium",
                "suggested_action": "deep_dive",  # This should be overridden to "reject"
                "action_reasoning": "Need deeper investigation"
            })
            mock_client.chat.completions.create.return_value = mock_response
            
            # Execute the reviewer node
            result_state = structured_data_reviewer_node(state)
            
            # Verify that the final action is not deep_dive
            final_action = result_state.metadata.get("next_step_after_structured_review")
            self.assertIn(final_action, ["accept", "reject"], 
                         f"Expected accept or reject after deep dive, got {final_action}")
            
            # Verify that if LLM suggested deep_dive, it was overridden to reject
            last_review = result_state.metadata.get("last_structured_review_details", {})
            if "deep_dive" in last_review.get("action_reasoning", "").lower():
                self.assertEqual(final_action, "reject", 
                               "Deep dive suggestion should be overridden to reject")
            
            # Verify final decision mode was triggered
            decision_log = result_state.decision_log[-1] if result_state.decision_log else {}
            self.assertTrue(decision_log.get("final_decision_mode", False),
                           "Final decision mode should be True after one deep dive")
            
            logger.info(f"Final decision test passed. Action: {final_action}, Deep dive count: {result_state.consecutive_deep_dive_count}")

    def test_structured_reviewer_initial_review_allows_deep_dive(self):
        """Test that initial review (no deep dives yet) allows deep_dive option."""
        # Use a copy of the initial state but ensure consecutive_deep_dive_count is 0
        state = create_initial_state(country_name=self.test_country, sector_name=self.test_sector)
        state.structured_data = self.initial_state.structured_data.copy()
        state.search_plan = self.initial_state.search_plan.copy()
        state.target_country_locode = "TL"
        state.consecutive_deep_dive_count = 0  # No deep dives performed yet
        
        # Mock OpenAI client to simulate LLM suggesting deep_dive
        with patch('agents.reviewer.OpenAI') as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            
            # Mock response suggesting deep_dive
            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps({
                "overall_assessment_notes": "Promising but need more data",
                "URL": "http://example.com",
                "subsector": "electricity",
                "relevance_score": "High",
                "relevance_reasoning": "Directly relevant to target",
                "credibility_score": "High",
                "credibility_reasoning": "Official government source",
                "completeness_score": "Medium",
                "completeness_reasoning": "Some details missing",
                "overall_confidence": "Medium",
                "suggested_action": "deep_dive", 
                "action_reasoning": "Need to explore sub-pages for detailed data",
                "refinement_details": "Focus on statistical tables and time series"
            })
            mock_client.chat.completions.create.return_value = mock_response
            
            # Execute the reviewer node
            result_state = structured_data_reviewer_node(state)
            
            # Verify that deep_dive action is allowed
            final_action = result_state.metadata.get("next_step_after_structured_review")
            self.assertEqual(final_action, "deep_dive", 
                           f"Expected deep_dive to be allowed in initial review, got {final_action}")
            
            # Verify refinement details are preserved
            refinement_details = result_state.metadata.get("refinement_details")
            self.assertIsNotNone(refinement_details, "Refinement details should be preserved for deep_dive")
            
            # Verify final decision mode was NOT triggered
            decision_log = result_state.decision_log[-1] if result_state.decision_log else {}
            self.assertFalse(decision_log.get("final_decision_mode", True),
                            "Final decision mode should be False for initial review")
            
            logger.info(f"Initial review test passed. Action: {final_action}, Deep dive count: {result_state.consecutive_deep_dive_count}")

if __name__ == '__main__':
    unittest.main() 