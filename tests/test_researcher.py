"""
Tests for the Researcher Agent.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, mock_open, call
import asyncio
import unittest
import logging
import os
import json
import config
from tenacity import stop_after_attempt, wait_none
import re
from pathlib import Path, WindowsPath
from datetime import datetime, timezone
import tempfile

# Import project modules
from agent_state import AgentState, create_initial_state
# Import node and specific async functions from researcher module
from agents.researcher import (
    researcher_node,
    collect_search_results,
)
# Import utility functions from utils module
from agents.utils import (
    needs_advanced_scraping,
    google_search_async, # Import Google search for mocking
)
from agents.utils.file_saver import sanitize_filename

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
def mock_search_results():
    """Fixture for mock search results."""
    return [
        {
            "url": "https://klimat.gov.pl/emisje",
            "title": "Emisje gazów cieplarnianych",
            "snippet": "Krajowa inwentaryzacja emisji gazów cieplarnianych"
        },
        {
            "url": "https://example.com/climate",
            "title": "Climate data",
            "snippet": "Various climate data and information"
        }
    ]

@pytest.mark.asyncio
async def test_collect_search_results_saves_output():
    """Test search results collection with mocked Google search and mocked file saving."""
    mock_search_data = [
        {"url": "https://klimat.gov.pl/emisje", "title": "Test Result 1"},
        {"url": "https://example.com/data", "title": "Test Result 2"}
    ]
    with patch('agents.researcher.google_search_async', new_callable=AsyncMock) as mock_google_search, \
         patch('os.makedirs') as mock_makedirs, \
         patch('builtins.open', new_callable=mock_open) as mock_file_open:
        
        mock_google_search.return_value = mock_search_data
        
        results = await collect_search_results(
            query="test query", 
            country_name="Testlandia",
            max_results=5, 
            save_raw_results=True,
            save_dir="logs/search_api_outputs"
        )
        mock_google_search.assert_called_once()
        assert len(results) == 2
        assert results[0]["url"] == "https://klimat.gov.pl/emisje"
        assert results[1]["url"] == "https://example.com/data"

        mock_makedirs.assert_called_once_with("logs/search_api_outputs", exist_ok=True)
        mock_file_open.assert_called_once()
        write_call_args = mock_file_open.call_args
        
        query_arg = "test query"
        search_engine_used_arg = "google"

        actual_path_norm = os.path.normpath(write_call_args[0][0])
        expected_dir_norm = os.path.normpath("logs/search_api_outputs")

        assert actual_path_norm.startswith(expected_dir_norm), \
                        f"Actual path '{actual_path_norm}' does not start with expected directory '{expected_dir_norm}'."
        assert os.path.basename(actual_path_norm).startswith(f"{search_engine_used_arg}_results_"), \
            f"Filename '{os.path.basename(actual_path_norm)}' does not start with expected prefix."
        assert actual_path_norm.endswith(".json"), \
            f"Filename '{actual_path_norm}' does not end with .json."
        
        assert write_call_args[0][1] == "w"
        assert write_call_args[1]['encoding'] == "utf-8"

        mock_file_handle = mock_file_open()
        written_content_str = "".join(call_arg[0][0] for call_arg in mock_file_handle.write.call_args_list)
        written_content_data = json.loads(written_content_str)
        assert written_content_data == mock_search_data

@pytest.mark.asyncio
async def test_collect_search_results_file_exclusions():
    """Test that collect_search_results correctly adds filetype exclusions for Google search."""
    base_query = "climate change data Chile"
    expected_exclusions = [
        "-filetype:pdf",
        "-filetype:xlsx", "-filetype:xls",
        "-filetype:docx", "-filetype:doc",
        "-filetype:pptx", "-filetype:ppt",
        "-filetype:zip"
    ]
    expected_google_query_parts = [base_query] + expected_exclusions

    with patch('agents.researcher.google_search_async', new_callable=AsyncMock) as mock_google:
        mock_google.return_value = [] # We don't care about results, just the call

        # Test with Google search (only option now)
        await collect_search_results(
            query=base_query,
            country_name="Chile",
            save_raw_results=False # No need to test saving here
        )
        mock_google.assert_called_once()
        called_google_query = mock_google.call_args[0][0]
        for part in expected_google_query_parts:
            assert part in called_google_query, f"Expected '{part}' in Google query '{called_google_query}'"

@pytest.mark.asyncio
async def test_collect_search_results_no_save_if_no_results():
    """Test search results collection with mocked Google search and mocked file saving."""
    mock_search_data = []
    with patch('agents.researcher.google_search_async', new_callable=AsyncMock) as mock_google_search, \
         patch('os.makedirs') as mock_makedirs, \
         patch('builtins.open', new_callable=mock_open) as mock_file_open:
        
        mock_google_search.return_value = mock_search_data
        
        results = await collect_search_results(
            query="test query", 
            country_name="Testlandia",
            max_results=5, 
            save_raw_results=True,
            save_dir="logs/search_api_outputs"
        )
        mock_google_search.assert_called_once()
        assert len(results) == 0

        mock_makedirs.assert_not_called()
        mock_file_open.assert_not_called()

class TestResearcherNode(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Setup that needs to run before each async test
        self.test_country = "Testlandia"
        self.test_sector = "stationary_energy"
        self.initial_state = create_initial_state(mode_name="emissions", which_name=self.test_sector, country_name=self.test_country)
        self.initial_state.target_country_locode = "TL"
        # Update search_plan items to include 'rank'
        self.initial_state.search_plan = [
            {"query": "Testlandia GHG report", "priority": "high", "status": "pending", "rank": 1},
            {"query": "Testlandia energy statistics", "priority": "medium", "status": "pending", "rank": 2}
        ]
        
        # Mock config attributes directly used by the node or its callees
        self.original_config_values = {}
        config_attrs_to_mock = {
            "MAX_RETRY_ATTEMPTS": 2,
            "MAX_QUERIES_PER_RESEARCH_CYCLE": 2,
            "GOOGLE_API_KEY": "mock_google_key",
            "GOOGLE_CSE_ID": "mock_cse_id",
            "OPENROUTER_API_KEY": "mock_openrouter_key",
            "MAX_RESULTS_PER_QUERY": 5,
            "MAX_GOOGLE_QUERIES_PER_RUN": 10,
            "RELEVANCE_CHECK_MODEL": "mock_relevance_model"
        }
        for attr, value in config_attrs_to_mock.items():
            if hasattr(config, attr):
                self.original_config_values[attr] = getattr(config, attr)
            setattr(config, attr, value)

    async def asyncTearDown(self):
        # Restore original config values after each test
        for attr, original_value in self.original_config_values.items():
            setattr(config, attr, original_value)

    @patch('agents.researcher.scrape_urls_async', new_callable=AsyncMock)
    @patch('agents.researcher.collect_search_results', new_callable=AsyncMock) # Mock collect_search_results fully
    @patch('os.makedirs') # Mock for researcher node's own output saving
    @patch('builtins.open', new_callable=mock_open) # Mock for researcher node's own output saving
    @patch('agents.researcher.AsyncOpenAI') # Mock the AsyncOpenAI client for relevance checking
    async def test_researcher_node_processes_plan_and_saves_outputs(self, mock_async_openai_client, mock_node_file_open, mock_node_makedirs, mock_collect_search_results, mock_scrape_urls_async):
        # Configure mock for AsyncOpenAI client used in relevance check
        mock_relevance_client_instance = mock_async_openai_client.return_value
        mock_relevance_completions = AsyncMock() # mock_relevance_client_instance.chat.completions
        mock_relevance_client_instance.chat = AsyncMock()
        mock_relevance_client_instance.chat.completions = mock_relevance_completions

        async def mock_relevance_side_effect(*args, **kwargs):
            # UPDATED: Return a JSON string matching RelevanceCheckOutput
            relevance_response_dict = {"is_relevant": True, "reason": "Mock relevance: YES for plan processing"}
            relevance_response_content = json.dumps(relevance_response_dict)
            mock_choice = MagicMock()
            mock_choice.message = MagicMock()
            mock_choice.message.content = relevance_response_content

            mock_completion_response = AsyncMock() # Simulate the completion object
            mock_completion_response.choices = [mock_choice]
            return mock_completion_response

        mock_relevance_completions.create = AsyncMock(side_effect=mock_relevance_side_effect)

        # Configure mocks for collect_search_results and scrape_urls_async
        async def mock_collect_side_effect(**kwargs):
            query = kwargs.get('query')
            if query == "Testlandia GHG report":
                return [
                    {"url": "https://klimat.gov.pl/emisje", "title": "Test Result 1", "snippet": "Snippet for GHG report..."},
                    {"url": "https://example.com/data", "title": "Test Result 2", "snippet": "Snippet for example data..."}
                ]
            elif query == "Testlandia energy statistics":
                return [
                    {"url": "https://stats.gov.tl/energy", "title": "Energy Stats", "snippet": "Snippet for energy stats..."}
                ]
            else:
                 # Default fallback if a different query is somehow processed
                 return []
        mock_collect_search_results.side_effect = mock_collect_side_effect

        # mock_scrape_urls_async.return_value = [
        #     {"url": "https://klimat.gov.pl/emisje", "content": "Example GHG content", "title": "Scraped GHG Report", "success": True, "markdown": "GHG md"},
        #     {"url": "https://stats.gov.tl/energy", "content": "Energy data content", "title": "Scraped Energy Stats", "success": True, "markdown": "Energy md"}
        # ]
        async def mock_scrape_side_effect_researcher(urls, state=None, **kwargs):
            results = []
            for i, url_item in enumerate(urls):
                # Simplified: return mock data for any URL passed in
                results.append({
                    'url': url_item,
                    'content': f'Mock content for {url_item}',
                    'title': f'Mock Title {i}',
                    'success': True,
                    'markdown': f'Mock Markdown for {url_item}'
                })
            return results
        mock_scrape_urls_async.side_effect = mock_scrape_side_effect_researcher
        
        # Run the node
        updated_state = await researcher_node(self.initial_state)
        
        # Verify state was updated
        self.assertGreater(len(updated_state.scraped_data), 0, "Should add documents to state.scraped_data")
        self.assertEqual(updated_state.search_plan[0]["status"], "searched")
        self.assertEqual(updated_state.search_plan[1]["status"], "searched")
        
        # Verify decision log was updated by researcher
        researcher_actions = [log.get('action') for log in updated_state.decision_log if log.get("agent") == "Researcher"]

        self.assertIn('research_iteration_completed', researcher_actions)

        # Verify final researcher output saving mocks were called
        # This checks the saving at the end of researcher_node
        # The researcher_node uses a module-level constant RESEARCHER_OUTPUT_DIR = "logs/researcher_outputs"
        expected_researcher_output_dir = os.path.join(os.getcwd(), "logs", "researcher_outputs")
        mock_node_makedirs.assert_called_with(expected_researcher_output_dir, exist_ok=True)
        
        # ADJUSTED ASSERTION: Only expect 1 call for the summary JSON written directly by researcher_node
        # The mock_node_file_open patches builtins.open as seen by researcher.py, not by file_saver.py
        self.assertEqual(mock_node_file_open.call_count, 1, "Expected 1 call for summary JSON.")

        # Verify that the researcher summary JSON was saved
        # The mock_node_file_open is used for this specific file
        # mock_node_makedirs.assert_any_call(os.path.normpath("logs/researcher_outputs"), exist_ok=True)
        # Find the call to open that saved the researcher summary
        
        researcher_summary_save_call = None
        for call_item in mock_node_file_open.call_args_list:
            # Check if the filename in the call matches the expected pattern
            if 'researcher_cycle_output' in os.path.basename(call_item.args[0]):
                researcher_summary_save_call = call_item
                break
        self.assertIsNotNone(researcher_summary_save_call, "Researcher cycle summary file was not saved.")
        if researcher_summary_save_call:
            self.assertTrue(researcher_summary_save_call.args[0].endswith('.json'))
        # Further checks on content could be added if needed

    @patch('agents.researcher.scrape_urls_async', new_callable=AsyncMock)
    @patch('agents.researcher.collect_search_results', new_callable=AsyncMock)
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('agents.researcher.AsyncOpenAI')
    async def test_researcher_node_deep_dive_scrape_action(self, mock_async_openai_client, mock_node_file_open, mock_node_makedirs, mock_collect_search_results, mock_scrape_urls_async):
        # Setup state with a deep dive scrape action
        self.initial_state.metadata["deep_dive_action"] = {"action_type": "scrape", "target": "http://example.com"}

        # Configure mock relevance check client
        mock_relevance_client_instance = mock_async_openai_client.return_value
        mock_relevance_client_instance.chat = AsyncMock()
        mock_relevance_client_instance.chat.completions = AsyncMock()
        # UPDATED: Return a JSON string matching RelevanceCheckOutput
        relevance_response_dict = {"is_relevant": True, "reason": "Mock relevance: YES for deep dive scrape"}
        relevance_response_content = json.dumps(relevance_response_dict)
        mock_relevance_client_instance.chat.completions.create.return_value = AsyncMock(
            choices=[MagicMock(message=MagicMock(content=relevance_response_content))]
        )

        # No search results returned from collect_search_results
        mock_collect_search_results.return_value = []

        # Mock scrape to return successful result
        mock_scrape_urls_async.return_value = [
            {"url": "http://example.com", "content": "mock", "success": True, "markdown": "mock"}
        ]

        updated_state = await researcher_node(self.initial_state)

        # mock_scrape_urls_async.assert_called_once_with(["http://example.com"])
        # CORRECTED ASSERTION: Check for urls keyword argument and allow other args implicitly or use ANY for state
        mock_scrape_urls_async.assert_called_once_with(urls=["http://example.com"], state=self.initial_state)
        self.assertTrue(any(doc.get("url") == "http://example.com" for doc in updated_state.scraped_data))

    @patch('agents.utils.file_saver.Path.mkdir')  # Mock for Path.mkdir in file_saver module
    @patch('agents.utils.file_saver.open', new_callable=mock_open)  # Mock for open in file_saver module
    # Patches for os.makedirs and open directly within agents.researcher (for summary)
    @patch('agents.researcher.os.makedirs') # Mock for os.makedirs in researcher module
    @patch('agents.researcher.open', new_callable=mock_open) # Mock for open in researcher module
    @patch('agents.researcher.scrape_urls_async', new_callable=AsyncMock)
    @patch('agents.researcher.collect_search_results', new_callable=AsyncMock)
    @patch('agents.researcher.AsyncOpenAI')
    async def test_researcher_node_saves_scraped_html_content(
        self, 
        mock_researcher_async_openai: MagicMock,      # Corresponds to @patch('agents.researcher.AsyncOpenAI')
        mock_researcher_collect_search_results: AsyncMock, # Corresponds to @patch('agents.researcher.collect_search_results', ...)
        mock_researcher_scrape_urls_async: AsyncMock,    # Corresponds to @patch('agents.researcher.scrape_urls_async', ...)
        mock_researcher_direct_open: MagicMock,         # Corresponds to @patch('agents.researcher.open', ...)
        mock_researcher_direct_os_makedirs: MagicMock,  # Corresponds to @patch('agents.researcher.os.makedirs')
        mock_filesaver_actual_modules_open: MagicMock,  # Corresponds to @patch('agents.utils.file_saver.open', ...)
        mock_filesaver_actual_modules_path_mkdir: MagicMock  # Corresponds to @patch('agents.utils.file_saver.Path.mkdir')
    ):
        """
        Test that researcher_node correctly scrapes a specific URL (Polish stats site)
        and attempts to save its HTML content using file_saver.save_scrape_to_file.
        This test focuses on the path from a URL being deemed relevant to it being scraped and saved.
        """
        test_url_to_scrape = "https://bdl.stat.gov.pl/bdl/dane/podgrup/temat"
        mock_html_content = "<html><body>Mock Polish Stats Data</body></html>"
        
        # --- Configure Mocks ---
        
        # 1. Mock collect_search_results (used by researcher_node)
        async def mock_collect_side_effect_for_save_test(**kwargs):
            return [{ "url": test_url_to_scrape, "title": "Polish Stats", "snippet": "BDL data..." }]
        mock_researcher_collect_search_results.side_effect = mock_collect_side_effect_for_save_test

        # 2. Mock Relevance Check (via AsyncOpenAI client, used by researcher_node)
        mock_relevance_client_instance = mock_researcher_async_openai.return_value
        mock_relevance_completions = AsyncMock()
        mock_relevance_client_instance.chat = AsyncMock()
        mock_relevance_client_instance.chat.completions = mock_relevance_completions
        async def mock_relevance_side_effect_for_save_test(*args, **kwargs):
            relevance_response_dict = {"is_relevant": True, "reason": f"Mock relevance: YES for {test_url_to_scrape}"}
            relevance_response_content = json.dumps(relevance_response_dict)
            mock_choice = MagicMock()
            mock_choice.message = MagicMock()
            mock_choice.message.content = relevance_response_content
            mock_completion_response = AsyncMock()
            mock_completion_response.choices = [mock_choice]
            return mock_completion_response
        mock_relevance_completions.create = AsyncMock(side_effect=mock_relevance_side_effect_for_save_test)

        # 3. Mock scrape_urls_async (used by researcher_node)
        async def mock_scrape_side_effect_for_save_test(urls, state=None, **kwargs):
            results = []
            for url_item in urls:
                if url_item == test_url_to_scrape:
                    results.append({
                        'url': url_item,
                        'html_content': mock_html_content,
                        'content': f'Mock markdown for {url_item}',
                        'title': f'Scraped {url_item}',
                        'success': True
                    })
                else:
                    results.append({
                        'url': url_item, 'html_content': None, 'content': 'Error content', 
                        'title': f'Scraped {url_item}', 'success': False
                    })
            return results
        mock_researcher_scrape_urls_async.side_effect = mock_scrape_side_effect_for_save_test

        # 4. Initial state setup
        self.initial_state.search_plan = [{ "query": "Search that finds Polish stats", "priority": "high", "status": "pending", "rank": 1 }]
        self.initial_state.target_country = "Poland"
        self.initial_state.target_which = "stationary_energy"
        if not self.initial_state.start_time:
             self.initial_state.start_time = datetime.now(timezone.utc).isoformat()

        # --- Run the node ---
        updated_state = await researcher_node(self.initial_state)

        # --- Assertions ---
        
        # Use the ACTUAL sanitization logic from researcher.py line 321-323
        raw_run_id = self.initial_state.start_time
        sanitized_run_id_from_time = raw_run_id.replace(":", "-").replace("T", "_").split(".")[0]
        current_run_id = sanitized_run_id_from_time
        
        # Assertions for operations within agents.utils.file_saver.save_scrape_to_file
        sanitized_sector = "Stationary Energy".replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        sane_country = sanitize_filename("Poland")
        sane_folder_name = sanitize_filename(f"{sanitized_sector}_{current_run_id}")
        sanitized_prefix = sanitize_filename("bdl.stat.gov.md.html")
        
        expected_full_path = WindowsPath(f"data/scrape_results/{sane_country}/{sane_folder_name}/{sanitized_prefix}")

        # Check the call to Path.mkdir within file_saver (mocked as mock_filesaver_actual_modules_path_mkdir)
        # save_scrape_to_file calls filepath.parent.mkdir(...), so we just verify it was called correctly
        mock_filesaver_actual_modules_path_mkdir.assert_called_once_with(parents=True, exist_ok=True)

        # Verify that mkdir was called once (we can't easily check the instance it was called on)
        self.assertEqual(mock_filesaver_actual_modules_path_mkdir.call_count, 1, "Path.mkdir in file_saver should be called once.")

        # Check the call to open within file_saver (mocked as mock_filesaver_actual_modules_open)
        mock_filesaver_actual_modules_open.assert_called_once_with(expected_full_path, "w", encoding="utf-8")
        mock_filesaver_actual_modules_open().write.assert_called_once_with(mock_html_content)

        # Assertions for researcher_node's direct file operations (e.g., summary saving)
        # These use mock_researcher_direct_os_makedirs and mock_researcher_direct_open
        mock_researcher_direct_os_makedirs.assert_called_with( # Use assert_called_with or assert_any_call as appropriate
            os.path.join(os.getcwd(), "logs", "researcher_outputs"), 
            exist_ok=True
        )
        self.assertTrue(mock_researcher_direct_open.called, "agents.researcher.open (for summary) was not called")

        # Check that the URL was added to scraped_data in the state
        found_in_scraped_data = False
        for item in updated_state.scraped_data:
            if item.get("url") == test_url_to_scrape:
                found_in_scraped_data = True
                self.assertEqual(item.get("html_content"), mock_html_content)
                self.assertEqual(item.get("saved_html_filepath"), str(expected_full_path))
                break
        self.assertTrue(found_in_scraped_data, f"Scraped data for {test_url_to_scrape} not found in updated_state.scraped_data")

    @patch('agents.utils.scraping.crawl_website')  # Remove new_callable=AsyncMock since crawl_website is sync
    @patch('agents.researcher.collect_search_results', new_callable=AsyncMock)
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('agents.researcher.AsyncOpenAI')
    async def test_researcher_node_deep_dive_crawl_action(self, mock_async_openai_client, mock_node_file_open, mock_node_makedirs, mock_collect_search_results, mock_crawl_website):
        # Setup state with a deep dive crawl action
        self.initial_state.metadata["deep_dive_action"] = {
            "action_type": "crawl", 
            "target": "https://docs.example.com",
            "max_pages": 15,
            "exclude_patterns": ["blog/*", "news/*"]
        }

        # Configure mock relevance check client  
        mock_relevance_client_instance = mock_async_openai_client.return_value
        mock_relevance_client_instance.chat = AsyncMock()
        mock_relevance_client_instance.chat.completions = AsyncMock()
        relevance_response_dict = {"is_relevant": True, "reason": "Mock relevance: YES for crawled pages"}
        relevance_response_content = json.dumps(relevance_response_dict)
        mock_relevance_client_instance.chat.completions.create.return_value = AsyncMock(
            choices=[MagicMock(message=MagicMock(content=relevance_response_content))]
        )

        # No search results returned from collect_search_results
        mock_collect_search_results.return_value = []

        # Mock crawl_website to return multiple successful results (sync function)
        mock_crawl_website.return_value = [
            {
                "url": "https://docs.example.com/page1", 
                "content": "Mock content 1", 
                "success": True,
                "title": "Page 1"
            },
            {
                "url": "https://docs.example.com/page2", 
                "content": "Mock content 2", 
                "success": True,
                "title": "Page 2"  
            },
            {
                "url": "https://docs.example.com/page3", 
                "content": "Mock content 3", 
                "success": True,
                "title": "Page 3"
            }
        ]

        updated_state = await researcher_node(self.initial_state)

        # Verify crawl_website was called with correct parameters
        mock_crawl_website.assert_called_once_with(
            base_url="https://docs.example.com",
            max_pages=15,
            exclude_patterns=["blog/*", "news/*"],
            state=self.initial_state
        )
        
        # Verify deep_dive_action was cleared from metadata after processing
        self.assertNotIn("deep_dive_action", updated_state.metadata)
        
        # Since we mocked crawl_website to return results but no actual scraping happens in this test,
        # the scraped_data won't contain these items unless we mock scrape_urls_async too.
        # But we can verify the crawl function was called correctly.

class TestResearcherUtils(unittest.TestCase):
    

    def test_needs_advanced_scraping(self):
        # Document links should need advanced scraping
        self.assertTrue(needs_advanced_scraping("https://example.com/doc.pdf"))
        self.assertTrue(needs_advanced_scraping("https://example.com/data.xlsx"))
        
        # JavaScript-heavy pages should need advanced scraping
        self.assertTrue(needs_advanced_scraping("https://example.com/#/dashboard"))
        
        # Regular pages should not need advanced scraping
        self.assertFalse(needs_advanced_scraping("https://example.com/page"))

# --- INTEGRATION TESTS WITH REAL CALLS (LIMITED TO 2 PAGES) ---

class TestResearcherIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests that use real API calls but with strict limits."""
    
    async def asyncSetUp(self):
        self.test_country = "TestCountry"
        self.test_sector = "stationary_energy"
        
        # Store original config values
        self.original_config_values = {}
        config_attrs_to_mock = {
            "MAX_QUERIES_PER_RESEARCH_CYCLE": 1,  # Limit to 1 query
            "MAX_RESULTS_PER_QUERY": 2,           # Limit to 2 results
            "ENABLE_PRE_SCRAPE_RELEVANCE_CHECK": False  # Disable to reduce LLM calls
        }
        for attr, value in config_attrs_to_mock.items():
            if hasattr(config, attr):
                self.original_config_values[attr] = getattr(config, attr)
            setattr(config, attr, value)

    async def asyncTearDown(self):
        # Restore original config values
        for attr, original_value in self.original_config_values.items():
            setattr(config, attr, original_value)

    @pytest.mark.integration
    async def test_researcher_real_crawl_integration_limited(self):
        """
        INTEGRATION TEST: Test researcher with real crawl action, limited to 2 pages.
        This test requires FIRECRAWL_API_KEY and makes real API calls.
        """
        import os
        
        # Skip if no real API key available
        if not os.getenv('FIRECRAWL_API_KEY'):
            pytest.skip("FIRECRAWL_API_KEY not set - skipping integration test")
        
        # Create initial state with crawl action
        initial_state = create_initial_state(mode_name="emissions", which_name=self.test_sector, country_name=self.test_country)
        initial_state.metadata["deep_dive_action"] = {
            "action_type": "crawl",
            "target": "https://httpbin.org",  # Safe test site
            "max_pages": 2,  # STRICT LIMIT
            "exclude_patterns": ["status/*", "delay/*", "redirect/*"]
        }
        initial_state.search_plan = []  # No regular search plan to avoid extra API calls
        
        # Setup real Firecrawl config
        original_firecrawl_key = getattr(config, 'FIRECRAWL_API_KEY', None)
        config.FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
        
        try:
            # Mock only the file saving operations to avoid I/O during tests
            with patch('agents.researcher.os.makedirs'), \
                 patch('agents.researcher.open', new_callable=mock_open):
                
                # Run researcher with real crawl
                updated_state = await researcher_node(initial_state)
                
                # Verify crawl action was processed and cleared
                self.assertNotIn("deep_dive_action", updated_state.metadata)
                
                # Verify some data was gathered (should be limited by our 2-page limit)
                # Note: The actual scraping happens via scrape_urls_async after crawl discovers URLs
                # So we're testing the URL discovery part here
                logger.info(f"Researcher integration test completed")
                logger.info(f"Scraped data items: {len(updated_state.scraped_data)}")
                
                # Should have decision log entries
                researcher_actions = [log for log in updated_state.decision_log if log.get("agent") == "Researcher"]
                self.assertGreater(len(researcher_actions), 0, "Should have researcher decision log entries")
                
        finally:
            # Restore original config
            if original_firecrawl_key:
                config.FIRECRAWL_API_KEY = original_firecrawl_key
            elif hasattr(config, 'FIRECRAWL_API_KEY'):
                delattr(config, 'FIRECRAWL_API_KEY')

    @pytest.mark.integration
    async def test_researcher_real_scrape_integration_limited(self):
        """
        INTEGRATION TEST: Test researcher with real scrape action, limited to 1 URL.
        This test requires FIRECRAWL_API_KEY and makes real API calls.
        """
        import os
        
        # Skip if no real API key available
        if not os.getenv('FIRECRAWL_API_KEY'):
            pytest.skip("FIRECRAWL_API_KEY not set - skipping integration test")
        
        # Create initial state with scrape action
        initial_state = create_initial_state(mode_name="emissions", which_name=self.test_sector, country_name=self.test_country)
        initial_state.metadata["deep_dive_action"] = {
            "action_type": "scrape",
            "target": "https://httpbin.org/html"  # Simple test endpoint
        }
        initial_state.search_plan = []  # No regular search plan
        
        # Setup real Firecrawl config
        original_firecrawl_key = getattr(config, 'FIRECRAWL_API_KEY', None)
        config.FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
        
        try:
            # Mock only the file saving operations
            with patch('agents.researcher.os.makedirs'), \
                 patch('agents.researcher.open', new_callable=mock_open), \
                 patch('agents.utils.file_saver.Path.mkdir'), \
                 patch('agents.utils.file_saver.open', new_callable=mock_open):
                
                # Run researcher with real scrape
                updated_state = await researcher_node(initial_state)
                
                # Verify scrape action was processed and cleared
                self.assertNotIn("deep_dive_action", updated_state.metadata)
                
                # Should have scraped the target URL
                scraped_urls = [item.get("url") for item in updated_state.scraped_data]
                self.assertIn("https://httpbin.org/html", scraped_urls)
                
                # Verify content was actually scraped
                target_item = next((item for item in updated_state.scraped_data 
                                  if item.get("url") == "https://httpbin.org/html"), None)
                self.assertIsNotNone(target_item, "Should have scraped the target URL")
                if target_item:
                    self.assertTrue(target_item.get("success"), "Scraping should have succeeded")
                    self.assertGreater(len(target_item.get("content", "")), 0, "Should have content")
                    
                    logger.info(f"Real scrape integration test completed")
                    logger.info(f"Scraped content length: {len(target_item.get('content', ''))} characters")
                
        finally:
            # Restore original config
            if original_firecrawl_key:
                config.FIRECRAWL_API_KEY = original_firecrawl_key
            elif hasattr(config, 'FIRECRAWL_API_KEY'):
                delattr(config, 'FIRECRAWL_API_KEY')

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 