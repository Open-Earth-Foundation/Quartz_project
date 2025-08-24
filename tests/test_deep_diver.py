import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock, call
from typing import Dict, Any, List
import json
import os
import tempfile
from pathlib import Path

from agent_state import AgentState, create_initial_state
from agents.deep_diver import deep_dive_processor_node
from agents.schemas import DeepDiveAction
from agents.utils.scraping import scrape_urls_async, crawl_website  # Import scraping functionality
import config # To access config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE
from tenacity import RetryError # For testing retry failures

# Configure logging for tests if not already picked up from global pytest config
import logging
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG) # Uncomment if specific debugging for this file is needed

# Helper to create a mock AgentState
def _create_test_state(
    refinement_details: str = "Default refinement details",
    current_actions: int = 0
) -> AgentState:
    state = create_initial_state(mode_name="hazards", which_name="heatwave", country_name="Testlandia")
    state.metadata = {}
    if refinement_details:
        state.metadata["refinement_details"] = refinement_details
    state.current_deep_dive_actions_count = current_actions
    return state

# Mock OpenAI client response objects
class MockChoice:
    def __init__(self, content: str):
        self.message = MagicMock()
        self.message.content = content

class MockCompletion:
    def __init__(self, choices: list):
        self.choices = choices

@pytest.fixture
def mock_openai_completions_create():
    """Mocks client.chat.completions.create"""
    with patch("agents.deep_diver.OpenAI") as mock_openai_constructor:
        mock_client_instance = mock_openai_constructor.return_value
        mock_create_method = mock_client_instance.chat.completions.create
        yield mock_create_method

@pytest.mark.asyncio
async def test_deep_diver_no_refinement_details(mock_openai_completions_create: MagicMock):
    state = _create_test_state(refinement_details="")
    updated_state = await deep_dive_processor_node(state)

    assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
    assert "No refinement details provided" in updated_state.metadata["deep_dive_action"]["justification"]
    mock_openai_completions_create.assert_not_called()
    assert len(updated_state.decision_log) == 2

@pytest.mark.asyncio
async def test_deep_diver_max_actions_reached(mock_openai_completions_create: MagicMock):
    with patch("agents.deep_diver.config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE", 2):
        state = _create_test_state(refinement_details="Test details", current_actions=2)
        updated_state = await deep_dive_processor_node(state)

        assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
        assert "Max actions per deep dive cycle reached" in updated_state.metadata["deep_dive_action"]["justification"]
        mock_openai_completions_create.assert_not_called()

@pytest.mark.asyncio
async def test_deep_diver_two_stage_success_scrape(mock_openai_completions_create: MagicMock):
    thinking_output = 'Some reasoning... Then: {"action_type": "scrape", "target": "http://example.com/scrape", "justification": "Scrape this from reasoning."}'
    structured_output_json = DeepDiveAction(action_type="scrape", target="http://example.com/scrape", justification="Scrape this from reasoning.").model_dump_json()

    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]),      # For thinking model
        MockCompletion(choices=[MockChoice(content=structured_output_json)]) # For structured model
    ]
    
    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Scrape example.com", current_actions=0)
        updated_state = await deep_dive_processor_node(state)

        assert mock_openai_completions_create.call_count == 2
        # Check first call (thinking model)
        first_call_args = mock_openai_completions_create.call_args_list[0]
        assert first_call_args[1]['model'] == "thinking-model"
        # Check second call (structured model)
        second_call_args = mock_openai_completions_create.call_args_list[1]
        assert second_call_args[1]['model'] == "structured-model"
        # Check that response_format has the correct structure (be flexible about schema details)
        response_format = second_call_args[1]['response_format']
        assert response_format['type'] == "json_schema"
        assert "json_schema" in response_format or "schema" in response_format  # Allow either format

        assert updated_state.metadata["deep_dive_action"]["action_type"] == "scrape"
        assert updated_state.metadata["deep_dive_action"]["target"] == "http://example.com/scrape"
        assert updated_state.current_deep_dive_actions_count == 1
        assert updated_state.decision_log[-1]["action"] == "scrape"

@pytest.mark.asyncio
async def test_deep_diver_two_stage_success_terminate(mock_openai_completions_create: MagicMock):
    thinking_output = 'Analysis shows no more useful URLs. {"action_type": "terminate_deep_dive", "justification": "No additional valuable URLs found."}'
    structured_output_json = DeepDiveAction(action_type="terminate_deep_dive", target=None, justification="No additional valuable URLs found.").model_dump_json()

    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]),
        MockCompletion(choices=[MockChoice(content=structured_output_json)])
    ]

    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Check for more data", current_actions=2)
        updated_state = await deep_dive_processor_node(state)

        assert mock_openai_completions_create.call_count == 2
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
        assert updated_state.metadata["deep_dive_action"]["target"] is None
        assert updated_state.current_deep_dive_actions_count == 2  # Should not increment for terminate
        assert updated_state.decision_log[-1]["action"] == "terminate_deep_dive"

@pytest.mark.asyncio
async def test_deep_diver_thinking_model_empty_response(mock_openai_completions_create: MagicMock):
    mock_openai_completions_create.return_value = MockCompletion(choices=[MockChoice(content="")]) # Only one call, fails early
    
    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Test empty thinking response")
        updated_state = await deep_dive_processor_node(state)

        mock_openai_completions_create.assert_called_once()
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
        assert "Thinking model returned empty content" in updated_state.metadata["deep_dive_action"]["justification"]

@pytest.mark.asyncio
async def test_deep_diver_structured_extraction_fails_all_retries(mock_openai_completions_create: MagicMock):
    thinking_output = 'Some reasoning... {"action_type": "scrape", "target": "http://example.com", "justification": "Valid action proposed."}'
    
    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]),      # Thinking model OK
        MockCompletion(choices=[MockChoice(content="Invalid JSON 1")]),   # Structured model fail 1
        MockCompletion(choices=[MockChoice(content="Invalid JSON 2")]),   # Structured model fail 2
        MockCompletion(choices=[MockChoice(content="Invalid JSON 3")])    # Structured model fail 3
    ]

    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Test structured extraction failure")
        updated_state = await deep_dive_processor_node(state)

        assert mock_openai_completions_create.call_count == 1 + 3 # 1 for thinking, 3 for structured retries
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
        assert "LLM response processing error: 1 validation error for DeepDiveAction" in updated_state.metadata["deep_dive_action"]["justification"]
        assert "Invalid JSON 3" in updated_state.metadata["deep_dive_action"]["justification"] # Check for the last invalid content

@pytest.mark.asyncio
async def test_deep_diver_structured_extraction_empty_response_retries_fail(mock_openai_completions_create: MagicMock):
    thinking_output = 'Some reasoning... {"action_type": "scrape", "target": "http://example.com", "justification": "Valid action proposed."}'
    
    # Simulate thinking model OK, structured model returns empty string for all 3 attempts
    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]), 
        MockCompletion(choices=[MockChoice(content="")]),  
        MockCompletion(choices=[MockChoice(content="")]),
        MockCompletion(choices=[MockChoice(content="")])
    ]

    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3
    
        state = _create_test_state(refinement_details="Test structured extraction empty response")
        updated_state = await deep_dive_processor_node(state)

        assert mock_openai_completions_create.call_count == 1 + 3 
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
        assert "LLM response processing error:" in updated_state.metadata["deep_dive_action"]["justification"]
        assert "Structured model returned empty content for JSON extraction" in updated_state.metadata["deep_dive_action"]["justification"]


@pytest.mark.asyncio
async def test_deep_diver_structured_extraction_retry_succeeds(mock_openai_completions_create: MagicMock):
    thinking_output = 'Reasoning... {"action_type": "scrape", "target": "https://example.com/scrape-test", "justification": "Scrape for testing retry."}'
    valid_structured_json = DeepDiveAction(action_type="scrape", target="https://example.com/scrape-test", justification="Scrape for testing retry.").model_dump_json()

    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]),      # Thinking model OK
        MockCompletion(choices=[MockChoice(content="Invalid JSON 1")]),     # Structured model fail 1
        MockCompletion(choices=[MockChoice(content=valid_structured_json)]) # Structured model succeed on retry 2
    ]

    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Test structured extraction retry success")
        updated_state = await deep_dive_processor_node(state)

        assert mock_openai_completions_create.call_count == 1 + 2  # 1 for thinking, 2 for structured (1 fail, 1 success)
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "scrape"
        assert updated_state.metadata["deep_dive_action"]["target"] == "https://example.com/scrape-test"
        assert updated_state.current_deep_dive_actions_count == 1
        assert updated_state.decision_log[-1]["action"] == "scrape"


@pytest.mark.asyncio
async def test_deep_diver_action_missing_target_after_structured_extraction(mock_openai_completions_create: MagicMock):
    thinking_output = 'Let\'s scrape something, but I forgot what. {"action_type": "scrape", "justification": "Scrape without target in thinking."}'
    # ^ Target might be missing in thinking model\'s JSON part
    structured_output_json = json.dumps({"action_type": "scrape", "target": "", "justification": "Scrape this."}) # Added empty target

    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]),
        MockCompletion(choices=[MockChoice(content=structured_output_json)])
    ]
    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Test missing target from structured output")
        updated_state = await deep_dive_processor_node(state)
    
        assert mock_openai_completions_create.call_count == 2
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
        assert "scrape action requires a target URL" in updated_state.metadata["deep_dive_action"]["justification"]
        assert updated_state.current_deep_dive_actions_count == 0

@pytest.mark.asyncio
async def test_deep_diver_no_thinking_model_configured(mock_openai_completions_create: MagicMock):
    with patch("agents.deep_diver.config.THINKING_MODEL", None):
        state = _create_test_state(refinement_details="Test no thinking model")
        updated_state = await deep_dive_processor_node(state)
    
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
        assert "No THINKING_MODEL configured" in updated_state.metadata["deep_dive_action"]["justification"]
        mock_openai_completions_create.assert_not_called()

@pytest.mark.asyncio
async def test_deep_diver_no_structured_model_configured(mock_openai_completions_create: MagicMock):
    thinking_output = 'Some reasoning... {"action_type": "scrape", "target": "http://example.com", "justification": "Valid action proposed."}'
    mock_openai_completions_create.return_value = MockCompletion(choices=[MockChoice(content=thinking_output)]) # Mock for first call

    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = None # Simulate no structured model
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3
        
        state = _create_test_state(refinement_details="Test no structured model")
        updated_state = await deep_dive_processor_node(state)
    
        # Thinking model is called once, then it fails before calling structured model
        mock_openai_completions_create.assert_called_once() 
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
        assert "No STRUCTURED_MODEL configured" in updated_state.metadata["deep_dive_action"]["justification"]
        
# Example of a test that would have previously checked direct JSON parsing from single LLM call
# This is now covered by the two-stage tests.
# @pytest.mark.asyncio
# async def test_deep_diver_llm_invalid_json_response_OLD(mock_openai_completions_create: MagicMock):
#     mock_openai_completions_create.return_value = MockCompletion(choices=[MockChoice(content="Not a valid JSON")])
    
#     with patch("agents.deep_diver.config") as mock_config:
#         # ... (config setup) ...
#         state = _create_test_state(refinement_details="Test invalid JSON", current_actions=0)
#         updated_state = await deep_dive_processor_node(state)
#         # ... assertions for termination due to parsing error from a single call ...

@pytest.mark.asyncio
async def test_deep_diver_scrape_action_saves_files_to_directory():
    """Integration test that verifies when deep diver recommends scraping, files are actually saved."""
    thinking_output = 'Let me scrape this URL. {"action_type": "scrape", "target": "https://httpbin.org/html", "justification": "Test scraping with file save verification."}'
    structured_output_json = DeepDiveAction(
        action_type="scrape", 
        target="https://httpbin.org/html", 
        justification="Test scraping with file save verification."
    ).model_dump_json()

    # Create a temporary directory for this test to avoid polluting the real logs directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_scraped_dir = Path(temp_dir) / "scraped_websites"
        temp_scraped_dir.mkdir(exist_ok=True)
        
        with patch("agents.utils.scraping.SCRAPED_DATA_LOG_DIR", temp_scraped_dir):
            with patch("agents.deep_diver.OpenAI") as mock_openai_constructor:
                mock_client_instance = mock_openai_constructor.return_value
                mock_create_method = mock_client_instance.chat.completions.create
                
                mock_create_method.side_effect = [
                    MockCompletion(choices=[MockChoice(content=thinking_output)]),
                    MockCompletion(choices=[MockChoice(content=structured_output_json)])
                ]
                
                with patch("agents.deep_diver.config") as mock_config:
                    mock_config.THINKING_MODEL = "thinking-model"
                    mock_config.STRUCTURED_MODEL = "structured-model"
                    mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3
                    
                    # Ensure the directory is empty before the test
                    assert len(list(temp_scraped_dir.iterdir())) == 0, "Test directory should start empty"
                    
                    # Run the deep diver
                    state = _create_test_state(refinement_details="Test scraping with file verification")
                    updated_state = await deep_dive_processor_node(state)
                    
                    # Verify deep diver returned scrape action
                    assert updated_state.metadata["deep_dive_action"]["action_type"] == "scrape"
                    assert updated_state.metadata["deep_dive_action"]["target"] == "https://httpbin.org/html"
                    
                    # Now actually execute the scraping action to test file saving
                    scrape_url = updated_state.metadata["deep_dive_action"]["target"]
                    
                    # Mock Firecrawl to simulate a successful scrape
                    with patch("agents.utils.scraping.FIRECRAWL_AVAILABLE", True):
                        with patch("agents.utils.scraping.config.FIRECRAWL_API_KEY", "test-key"):
                            with patch("agents.utils.scraping.FirecrawlApp") as mock_firecrawl:
                                # Create a simple class to simulate Firecrawl response without MagicMock issues
                                class MockFirecrawlResponse:
                                    def __init__(self):
                                        self.markdown = "# Test HTML Content\nThis is test content from httpbin."
                                        self.html = "<html><body><h1>Test</h1></body></html>"
                                        self.metadata = {"title": "Test Page", "description": "Test description"}
                                
                                mock_response = MockFirecrawlResponse()
                                
                                mock_firecrawl_instance = mock_firecrawl.return_value
                                mock_firecrawl_instance.scrape_url.return_value = mock_response
                                
                                # Execute the scraping
                                scrape_results = await scrape_urls_async([scrape_url], state)
                                
                                # Verify scraping was successful
                                assert len(scrape_results) == 1
                                assert scrape_results[0]["success"] is True
                                assert scrape_results[0]["url"] == scrape_url
                                
                                # Verify files were saved to the directory
                                saved_files = list(temp_scraped_dir.iterdir())
                                assert len(saved_files) > 0, "Directory should not be empty after scraping"
                                
                                # Verify at least one markdown file was created for our URL
                                md_files = [f for f in saved_files if f.suffix == '.md']
                                assert len(md_files) > 0, "At least one markdown file should be created"
                                
                                # Verify the content of the saved markdown file
                                saved_file = md_files[0]
                                with open(saved_file, 'r', encoding='utf-8') as f:
                                    saved_content = f.read()
                                
                                # Check for YAML frontmatter and content
                                assert "---" in saved_content, "File should have YAML frontmatter"
                                assert "url: https://httpbin.org/html" in saved_content
                                assert "title: Test Page" in saved_content
                                assert "# Scraped Content from https://httpbin.org/html" in saved_content
                                assert mock_response.markdown in saved_content
                                
                                logger.info(f"Test verified: {len(saved_files)} files saved to {temp_scraped_dir}")

@pytest.mark.asyncio
async def test_deep_diver_scrape_action_file_save_error_handling():
    """Test that file saving errors are handled gracefully during scraping."""
    thinking_output = 'Scrape this. {"action_type": "scrape", "target": "https://example.com", "justification": "Test error handling."}'
    structured_output_json = DeepDiveAction(
        action_type="scrape", 
        target="https://example.com", 
        justification="Test error handling."
    ).model_dump_json()

    # Create a temporary directory but make it read-only to simulate write errors
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_scraped_dir = Path(temp_dir) / "scraped_websites"
        temp_scraped_dir.mkdir(exist_ok=True)
        
        with patch("agents.utils.scraping.SCRAPED_DATA_LOG_DIR", temp_scraped_dir):
            with patch("agents.deep_diver.OpenAI") as mock_openai_constructor:
                mock_client_instance = mock_openai_constructor.return_value
                mock_create_method = mock_client_instance.chat.completions.create
                
                mock_create_method.side_effect = [
                    MockCompletion(choices=[MockChoice(content=thinking_output)]),
                    MockCompletion(choices=[MockChoice(content=structured_output_json)])
                ]
                
                with patch("agents.deep_diver.config") as mock_config:
                    mock_config.THINKING_MODEL = "thinking-model"
                    mock_config.STRUCTURED_MODEL = "structured-model"
                    mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3
                    
                    state = _create_test_state(refinement_details="Test error handling in file saving")
                    updated_state = await deep_dive_processor_node(state)
                    
                    # Verify deep diver returned scrape action
                    assert updated_state.metadata["deep_dive_action"]["action_type"] == "scrape"
                    
                    # Simulate file saving error by making the directory unwritable
                    with patch("agents.utils.scraping.FIRECRAWL_AVAILABLE", True):
                        with patch("agents.utils.scraping.config.FIRECRAWL_API_KEY", "test-key"):
                            with patch("agents.utils.scraping.FirecrawlApp") as mock_firecrawl:
                                mock_response = MagicMock()
                                mock_response.markdown = "Test content"
                                mock_response.html = "<html></html>"
                                mock_response.metadata = {}
                                
                                # Make model_dump raise an exception to simulate serialization error
                                mock_response.model_dump.side_effect = Exception("Serialization error")
                                
                                mock_firecrawl_instance = mock_firecrawl.return_value
                                mock_firecrawl_instance.scrape_url.return_value = mock_response
                                
                                # Execute scraping - should handle the error gracefully
                                scrape_url = updated_state.metadata["deep_dive_action"]["target"]
                                scrape_results = await scrape_urls_async([scrape_url], state)
                                
                                # Verify scraping still reports success even if file saving fails
                                # (the scraping itself succeeded, just the logging failed)
                                assert len(scrape_results) == 1
                                assert scrape_results[0]["success"] is True

@pytest.mark.asyncio
async def test_deep_diver_crawl_action_success(mock_openai_completions_create: MagicMock):
    """Test successful crawl action generation."""
    thinking_output = '''
    The refinement asks for comprehensive documentation. I should crawl the entire docs section.
    {"action_type": "crawl", "target": "https://docs.example.com", "max_pages": 25, "exclude_patterns": ["blog/*", "news/*"], "justification": "Crawl docs section for comprehensive coverage."}
    '''
    structured_output_json = DeepDiveAction(
        action_type="crawl", 
        target="https://docs.example.com",
        max_pages=25,
        exclude_patterns=["blog/*", "news/*"],
        justification="Crawl docs section for comprehensive coverage."
    ).model_dump_json()

    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]),
        MockCompletion(choices=[MockChoice(content=structured_output_json)])
    ]
    
    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Need comprehensive documentation coverage", current_actions=0)
        updated_state = await deep_dive_processor_node(state)

        assert mock_openai_completions_create.call_count == 2
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "crawl"
        assert updated_state.metadata["deep_dive_action"]["target"] == "https://docs.example.com"
        assert updated_state.metadata["deep_dive_action"]["max_pages"] == 25
        assert updated_state.metadata["deep_dive_action"]["exclude_patterns"] == ["blog/*", "news/*"]
        assert updated_state.current_deep_dive_actions_count == 1
        assert updated_state.decision_log[-1]["action"] == "crawl"


@pytest.mark.asyncio
async def test_deep_diver_crawl_action_max_pages_capped(mock_openai_completions_create: MagicMock):
    """Test that crawl action max_pages is capped at 50 for safety."""
    thinking_output = '''
    Crawl with excessive pages.
    {"action_type": "crawl", "target": "https://massive-site.com", "max_pages": 200, "justification": "Crawl massive site."}
    '''
    # Note: The validation in deep_diver will cap this at 50
    structured_output_json = DeepDiveAction(
        action_type="crawl", 
        target="https://massive-site.com",
        max_pages=200,  # This will be capped
        justification="Crawl massive site."
    ).model_dump_json()

    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]),
        MockCompletion(choices=[MockChoice(content=structured_output_json)])
    ]
    
    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Crawl large site", current_actions=0)
        updated_state = await deep_dive_processor_node(state)

        assert updated_state.metadata["deep_dive_action"]["action_type"] == "crawl"
        assert updated_state.metadata["deep_dive_action"]["max_pages"] == 50  # Should be capped


@pytest.mark.asyncio
async def test_deep_diver_crawl_action_missing_target(mock_openai_completions_create: MagicMock):
    """Test that crawl action without target is converted to terminate."""
    thinking_output = '''
    Should crawl but missing target.
    {"action_type": "crawl", "max_pages": 10, "justification": "Crawl without target."}
    '''
    structured_output_json = json.dumps({
        "action_type": "crawl",
        "max_pages": 10,
        "justification": "Crawl without target."
        # Note: missing target field
    })

    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]),
        MockCompletion(choices=[MockChoice(content=structured_output_json)])
    ]
    
    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Test crawl without target", current_actions=0)
        updated_state = await deep_dive_processor_node(state)

        # Should be converted to terminate because crawl requires target
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
        assert "crawl action requires a target URL" in updated_state.metadata["deep_dive_action"]["justification"]
        assert updated_state.current_deep_dive_actions_count == 0  # Should not increment


@pytest.mark.asyncio
async def test_deep_diver_crawl_default_parameters(mock_openai_completions_create: MagicMock):
    """Test crawl action with default parameters (no max_pages or exclude_patterns specified)."""
    thinking_output = '''
    Simple crawl with defaults.
    {"action_type": "crawl", "target": "https://simple-site.com", "justification": "Basic crawl with defaults."}
    '''
    structured_output_json = DeepDiveAction(
        action_type="crawl", 
        target="https://simple-site.com",
        justification="Basic crawl with defaults."
        # Note: max_pages and exclude_patterns not specified, should use defaults
    ).model_dump_json()

    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]),
        MockCompletion(choices=[MockChoice(content=structured_output_json)])
    ]
    
    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Simple crawl test", current_actions=0)
        updated_state = await deep_dive_processor_node(state)

        assert updated_state.metadata["deep_dive_action"]["action_type"] == "crawl"
        assert updated_state.metadata["deep_dive_action"]["target"] == "https://simple-site.com"
        # Should have default max_pages (10) since not specified
        assert updated_state.metadata["deep_dive_action"].get("max_pages", 10) == 10
        assert updated_state.current_deep_dive_actions_count == 1


@pytest.mark.asyncio 
async def test_deep_diver_invalid_action_type_converted_to_terminate(mock_openai_completions_create: MagicMock):
    """Test that invalid action types are converted to terminate_deep_dive."""
    thinking_output = '''
    Invalid action type.
    {"action_type": "invalid_action", "target": "https://example.com", "justification": "This is invalid."}
    '''
    structured_output_json = json.dumps({
        "action_type": "invalid_action",
        "target": "https://example.com", 
        "justification": "This is invalid."
    })

    mock_openai_completions_create.side_effect = [
        MockCompletion(choices=[MockChoice(content=thinking_output)]),       # Thinking model call
        MockCompletion(choices=[MockChoice(content=structured_output_json)]), # 1st structured attempt
        MockCompletion(choices=[MockChoice(content=structured_output_json)]), # 2nd structured attempt (retry)
        MockCompletion(choices=[MockChoice(content=structured_output_json)])  # 3rd structured attempt (retry)
    ]
    
    with patch("agents.deep_diver.config") as mock_config:
        mock_config.THINKING_MODEL = "thinking-model"
        mock_config.STRUCTURED_MODEL = "structured-model"
        mock_config.MAX_ACTIONS_PER_DEEP_DIVE_CYCLE = 3

        state = _create_test_state(refinement_details="Test invalid action", current_actions=0)
        updated_state = await deep_dive_processor_node(state)

        # Should be converted to terminate because action type is invalid (caught by Pydantic validation)
        assert updated_state.metadata["deep_dive_action"]["action_type"] == "terminate_deep_dive"
        assert "LLM response processing error" in updated_state.metadata["deep_dive_action"]["justification"]
        assert "validation error for DeepDiveAction" in updated_state.metadata["deep_dive_action"]["justification"]
        assert updated_state.current_deep_dive_actions_count == 0  # Should not increment


# --- REAL FIRECRAWL INTEGRATION TESTS (LIMITED TO 2 PAGES MAX) ---

@pytest.mark.integration  
@pytest.mark.asyncio
async def test_real_firecrawl_crawl_integration_strict_limits():
    """
    REAL INTEGRATION TEST: Test actual Firecrawl crawl_url with strict 2-page limit.
    This test requires FIRECRAWL_API_KEY to be set and makes real API calls.
    """
    pytest.importorskip("firecrawl", reason="Firecrawl not available for integration test")
    
    if not config.FIRECRAWL_API_KEY:
        pytest.skip("FIRECRAWL_API_KEY not set - skipping real integration test")
    
    # Import the real function
    from agents.utils.scraping import crawl_website
    
    # Test with a small, reliable website and STRICT 2-page limit
    test_url = "https://httpbin.org"  # Reliable test site with limited pages
    
    logger.info("=== STARTING REAL FIRECRAWL CRAWL INTEGRATION TEST ===")
    logger.info(f"Testing crawl of {test_url} with 2-page limit")
    
    # Call the real crawl function with strict safety limits
    crawl_results = crawl_website(
        base_url=test_url,
        max_pages=2,  # STRICT LIMIT: Only 2 pages maximum
        timeout_minutes=1,  # STRICT TIMEOUT: Only 1 minute
        exclude_patterns=['*.pdf', '*.zip', 'admin/*']  # Basic excludes
    )
    
    # Verify results
    assert isinstance(crawl_results, list), "Should return a list of results"
    assert len(crawl_results) <= 2, f"Should crawl maximum 2 pages, got {len(crawl_results)}"
    
    if crawl_results:  # If any pages were successfully crawled
        for result in crawl_results:
            assert isinstance(result, dict), "Each result should be a dictionary"
            assert "url" in result, "Each result should have a URL"
            assert "content" in result, "Each result should have content"
            assert "success" in result, "Each result should have success status"
            assert result["success"] is True, "Crawled pages should be successful"
            assert len(result["content"]) > 0, "Content should not be empty"
            
        logger.info(f"✅ Real crawl integration test PASSED: {len(crawl_results)} pages crawled")
        logger.info(f"URLs crawled: {[r['url'] for r in crawl_results]}")
    else:
        logger.warning("⚠️ No pages were crawled - this may be expected for some sites")


@pytest.mark.integration
@pytest.mark.asyncio  
async def test_real_firecrawl_scrape_integration_single_page():
    """
    REAL INTEGRATION TEST: Test actual Firecrawl scrape_url_async with 1 page.
    """
    pytest.importorskip("firecrawl", reason="Firecrawl not available for integration test")
    
    if not config.FIRECRAWL_API_KEY:
        pytest.skip("FIRECRAWL_API_KEY not set - skipping real integration test")
    
    # Import the real function
    from agents.utils.scraping import scrape_urls_async
    
    # Test with a single reliable URL
    test_urls = ["https://httpbin.org/html"]  # Simple test page with basic HTML
    
    logger.info("=== STARTING REAL FIRECRAWL SCRAPE INTEGRATION TEST ===")
    logger.info(f"Testing scrape of {test_urls[0]}")
    
    # Call the real scrape function
    scrape_results = await scrape_urls_async(test_urls)
    
    # Verify results
    assert isinstance(scrape_results, list), "Should return a list of results"
    assert len(scrape_results) == 1, "Should have exactly one result"
    
    result = scrape_results[0]
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "url" in result, "Result should have a URL"
    assert "success" in result, "Result should have success status"
    
    if result["success"]:
        assert "content" in result, "Successful result should have content"
        assert len(result["content"]) > 0, "Content should not be empty"
        logger.info(f"✅ Real scrape integration test PASSED")
        logger.info(f"Content length: {len(result['content'])} characters")
    else:
        logger.warning(f"⚠️ Scrape failed: {result.get('error', 'Unknown error')}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_firecrawl_crawl_safety_timeouts():
    """
    REAL INTEGRATION TEST: Test that crawl safety limits (timeouts) work properly.
    """
    pytest.importorskip("firecrawl", reason="Firecrawl not available for integration test")
    
    if not config.FIRECRAWL_API_KEY:
        pytest.skip("FIRECRAWL_API_KEY not set - skipping real integration test")
    
    from agents.utils.scraping import crawl_website
    import time
    
    # Test with an extremely short timeout to verify safety limits work
    test_url = "https://httpbin.org"
    
    logger.info("=== TESTING CRAWL SAFETY TIMEOUTS ===")
    
    start_time = time.time()
    
    # This should complete quickly due to the small site and limits
    crawl_results = crawl_website(
        base_url=test_url,
        max_pages=1,  # Only 1 page
        timeout_minutes=1,  # 1 minute timeout (should be plenty)
    )
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Verify the operation completed in reasonable time (under 60 seconds)
    assert elapsed_time < 60, f"Crawl took too long: {elapsed_time:.2f} seconds"
    
    # Verify results
    assert isinstance(crawl_results, list), "Should return a list"
    assert len(crawl_results) <= 1, "Should respect the 1-page limit"
    
    logger.info(f"✅ Safety timeout test PASSED: completed in {elapsed_time:.2f} seconds")


@pytest.mark.integration
def test_real_firecrawl_crawl_page_limit_enforcement():
    """
    REAL INTEGRATION TEST: Test that page limits are strictly enforced.
    """
    pytest.importorskip("firecrawl", reason="Firecrawl not available for integration test")
    
    if not config.FIRECRAWL_API_KEY:
        pytest.skip("FIRECRAWL_API_KEY not set - skipping real integration test")
    
    from agents.utils.scraping import crawl_website
    
    # Test with a tiny limit to verify enforcement
    test_url = "https://httpbin.org"
    
    logger.info("=== TESTING PAGE LIMIT ENFORCEMENT ===")
    
    # Test with max_pages=1 - should never exceed this
    crawl_results = crawl_website(
        base_url=test_url,
        max_pages=1,  # STRICT: Only 1 page
        timeout_minutes=1
    )
    
    # Verify strict enforcement
    assert isinstance(crawl_results, list), "Should return a list"
    assert len(crawl_results) <= 1, f"VIOLATION: Got {len(crawl_results)} pages, expected ≤ 1"
    
    logger.info(f"✅ Page limit enforcement PASSED: {len(crawl_results)} pages (limit: 1)")


# --- UNIT TESTS WITH MOCKS (EXISTING) ---
