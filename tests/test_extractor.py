"""
Tests for the Data Extraction Agent.
"""
import pytest
from unittest.mock import patch, MagicMock, ANY
import json
import os
from pathlib import Path

# Import project modules
from agent_state import AgentState, create_initial_state
from agents.extractor import (
    extractor_node,
    extract_from_document,
    extract_with_llm,
    load_ghgi_sectors_info,
    ExtractorOutputSchema
)
from pydantic import ValidationError

def test_extractor_output_schema():
    """Test the ExtractorOutputSchema Pydantic model functionality."""
    assert "name" in ExtractorOutputSchema.model_fields
    assert "url" in ExtractorOutputSchema.model_fields
    # Add more assertions for other fields if necessary based on ExtractorOutputSchema

    # Test creation with minimally required fields (all are optional in ExtractorOutputSchema)
    item = ExtractorOutputSchema()
    assert item.name is None

    # Test with some fields
    item_full = ExtractorOutputSchema(
        name="Full Dataset",
        url="http://example.com/full",
        method_of_access="api",
        sector="Energy",
        subsector="Electricity",
        data_format="JSON",
        description="Detailed energy data.",
        granularity="regional",
        country="Testlandia",
        country_locode="TA"
    )
    assert item_full.sector == "Energy"
    assert item_full.name == "Full Dataset"

def test_load_ghgi_sectors_info():
    """Test loading GHGI sectors information."""
    sectors_info = load_ghgi_sectors_info()
    assert "Energy" in sectors_info
    assert "IPPU" in sectors_info
    assert "AFOLU" in sectors_info
    assert "Waste" in sectors_info

def test_extract_from_document():
    """Test basic document extraction without LLM."""
    test_document = {
        "url": "https://example.com/ghgi-data",
        "content": "This is a test document with some greenhouse gas inventory data."
    }
    
    extracted_data = extract_from_document(test_document, target_country="Poland", target_locode="PL")
    
    assert extracted_data["url"] == "https://example.com/ghgi-data"
    assert extracted_data["country"] == "Poland"
    assert extracted_data["country_locode"] == "PL"

@patch('openai.OpenAI')
def test_extract_with_llm_successful(mock_openai):
    """Test LLM-based extraction with a mocked OpenAI client - successful case."""
    mock_client_instance = MagicMock()
    mock_openai.return_value = mock_client_instance
    
    # Consistent mock structure for chat.completions.create
    mock_completion_message = MagicMock()
    # Ensure the mock content is a valid JSON string for ExtractorOutputSchema
    mock_completion_message.content = json.dumps({
        "name": "Polish Energy Statistics",
        "method_of_access": "downloadable file", 
        "sector": "Energy", 
        "subsector": "Fuel Combustion", 
        "data_format": "PDF", 
        "description": "Annual energy statistics for Poland", 
        "granularity": "national"
        # url, country, country_locode are added by extract_with_llm
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_completion_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client_instance.chat.completions.create.return_value = mock_response
    
    test_document = {
        "url": "https://example.com/energy",
        "content": "Annual energy statistics report for Poland covering fuel combustion in the energy sector."
    }
    
    extracted_data = extract_with_llm(test_document, target_country="Poland", target_locode="PL")
    
    assert extracted_data is not None, "extract_with_llm returned None on success"
    assert extracted_data["name"] == "Polish Energy Statistics"
    assert extracted_data["sector"] == "Energy"
    assert extracted_data["subsector"] == "Fuel Combustion"
    assert extracted_data["country"] == "Poland" # Added by extract_with_llm
    assert extracted_data["country_locode"] == "PL" # Added by extract_with_llm
    assert extracted_data["url"] == "https://example.com/energy" # Added by extract_with_llm
    mock_client_instance.chat.completions.create.assert_called_once()

@patch('agents.extractor.load_extractor_prompt_template', return_value="Test prompt {content} {ghgi_sectors_info} {prompt_fields_description} {url} {target_country_or_unknown}")
@patch('agents.extractor.load_ghgi_sectors_info', return_value="Test sector info")
@patch('openai.OpenAI')
class TestExtractWithLLMVariations:

    def test_extract_with_llm_malformed_json_response(self, mock_openai, mock_sectors_info, mock_prompt_template):
        """Test LLM extraction when LLM returns malformed JSON."""
        mock_client_instance = MagicMock()
        mock_openai.return_value = mock_client_instance
        
        mock_completion_message = MagicMock()
        mock_completion_message.content = '{"name": "Test Data", "sector": "Energy",,}' # Malformed JSON
        mock_choice = MagicMock()
        mock_choice.message = mock_completion_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_response
        
        test_document = {"url": "http://example.com/malformed", "content": "Some content"}
        # Capture logs to check for error logging
        with patch('logging.Logger.error') as mock_log_error:
            extracted_data = extract_with_llm(test_document, "Testland", "TL")
            assert extracted_data is None
            mock_log_error.assert_called_with(ANY, exc_info=True) # Check that an error was logged with exception info

    def test_extract_with_llm_empty_response(self, mock_openai, mock_sectors_info, mock_prompt_template):
        """Test LLM extraction when LLM returns an empty string."""
        mock_client_instance = MagicMock()
        mock_openai.return_value = mock_client_instance
        
        mock_completion_message = MagicMock()
        mock_completion_message.content = '' # Empty response
        mock_choice = MagicMock()
        mock_choice.message = mock_completion_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_response
        
        test_document = {"url": "http://example.com/empty_resp", "content": "Some content"}
        with patch('logging.Logger.warning') as mock_log_warning:
            extracted_data = extract_with_llm(test_document, "Testland", "TL")
            assert extracted_data is None
            mock_log_warning.assert_called_with(ANY)

    def test_extract_with_llm_empty_input_content(self, mock_openai, mock_sectors_info, mock_prompt_template):
        """Test LLM extraction when the input document content is empty."""
        test_document = {"url": "http://example.com/empty_content", "content": ""}
        
        # extract_with_llm should return None before trying to call OpenAI
        mock_client_instance = mock_openai.return_value
        with patch('logging.Logger.warning') as mock_log_warning:
            extracted_data = extract_with_llm(test_document, "Testland", "TL")
            assert extracted_data is None
            mock_client_instance.chat.completions.create.assert_not_called()
            mock_log_warning.assert_called_with("No content found in document for URL: http://example.com/empty_content. Skipping LLM extraction.")

    def test_extract_with_llm_missing_prompt_template(self, mock_openai, mock_sectors_info, mock_prompt_template_func):
        """Test LLM extraction when the main prompt template fails to load."""
        mock_prompt_template_func.return_value = "" # Simulate prompt template loading failure
        
        test_document = {"url": "http://example.com/missing_prompt", "content": "Some data"}
        mock_client_instance = mock_openai.return_value
        with patch('logging.Logger.error') as mock_log_error:
            extracted_data = extract_with_llm(test_document, "Testland", "TL")
            assert extracted_data is None
            mock_client_instance.chat.completions.create.assert_not_called()
            mock_log_error.assert_called_with("Extractor prompt template failed to load. Aborting LLM extraction.")
            
    # TODO: Add test for json_schema vs json_object fallback if possible by manipulating create() exceptions

@patch('agents.extractor.extract_with_llm')
def test_extractor_node(mock_extract_with_llm):
    """Test the extractor node functionality in a LangGraph workflow."""
    # Mock the LLM extraction function
    mock_extract_with_llm.return_value = {
        "name": "Test Dataset",
        "url": "https://example.com/ghgi",
        "sector": "Energy",
        "country": "Poland",
        "country_locode": "PL"
    }
    
    # Create initial state with test documents and sector
    initial_state = create_initial_state(country_name="Poland", sector_name="energy")
    initial_state.scraped_data = [
        {"url": "https://example.com/ghgi", "content": "Carbon dioxide emissions from energy sector..."}
    ]

    # Run the extractor node
    updated_state = extractor_node(initial_state)
    
    # Verify the state was updated correctly
    assert len(updated_state.structured_data) == 1  # Should have extracted data from the single document
    assert updated_state.structured_data[0]["url"] == "https://example.com/ghgi"
    
    # Check decision log was updated
    assert any(log.get('action') == 'extraction_complete' for log in updated_state.decision_log)
    
    # The extraction function should have been called for each document
    assert mock_extract_with_llm.call_count == 1

if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 