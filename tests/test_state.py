"""
Tests for the AgentState class.
"""
import json
import pytest
from dataclasses import asdict

# Import project modules (handled by conftest.py)
from agent_state import (
    AgentState, 
    reduce_list_field, 
    reduce_confidence_scores, 
    reduce_iteration_count,
    create_initial_state,
)

def test_agent_state_creation(sample_state):
    """Test basic creation of an AgentState instance."""
    # Test the fixture-provided state
    expected_prompt = "CCRA Mode: emissions, Type: stationary_energy, Country: Test Country Fixture"
    assert sample_state.prompt == expected_prompt, f"Prompt should be '{expected_prompt}' based on fixture"
    assert sample_state.target_country == "Test Country Fixture"
    assert sample_state.target_which == "stationary_energy"
    assert isinstance(sample_state.start_time, str), "Start time should be a string"
    assert sample_state.search_plan == [], "Search plan should start empty"
    assert sample_state.iteration_count == 0, "Iteration count should start at 0"
    
    # Create a custom state for additional testing
    prompt = "Find the latest greenhouse gas emissions data for Poland"
    state = AgentState(prompt=prompt)
    
    assert state.prompt == prompt, "Prompt should match the input"
    assert isinstance(state.start_time, str), "Start time should be a string"
    assert state.search_plan == [], "Search plan should start empty"
    assert state.iteration_count == 0, "Iteration count should start at 0"

def test_list_reducers():
    """Test the list field reducers."""
    state1 = AgentState(
        prompt="Test prompt",
        search_plan=[{"query": "test1"}],
        urls=[{"url": "http://example1.com"}]
    )
    
    state2 = AgentState(
        prompt="Test prompt",
        search_plan=[{"query": "test2"}],
        urls=[{"url": "http://example2.com"}]
    )
    
    # Test search_plan reducer
    search_plan_reducer = reduce_list_field("search_plan")
    combined_plan = search_plan_reducer(state1, state2)
    
    assert len(combined_plan) == 2, "Combined plan should have 2 items"
    assert combined_plan[0]["query"] == "test1", "First item should be from state1"
    assert combined_plan[1]["query"] == "test2", "Second item should be from state2"
    
    # Test urls reducer
    urls_reducer = reduce_list_field("urls")
    combined_urls = urls_reducer(state1, state2)
    
    assert len(combined_urls) == 2, "Combined urls should have 2 items"
    assert combined_urls[0]["url"] == "http://example1.com", "First url should be from state1"
    assert combined_urls[1]["url"] == "http://example2.com", "Second url should be from state2"

def test_confidence_scores_reducer():
    """Test the confidence scores reducer."""
    state1 = AgentState(
        prompt="Test prompt",
        confidence_scores={"data_quality": 0.7, "source_reliability": 0.8}
    )
    
    state2 = AgentState(
        prompt="Test prompt",
        confidence_scores={"data_quality": 0.9, "data_completeness": 0.6}
    )
    
    combined_scores = reduce_confidence_scores(state1, state2)
    
    assert combined_scores["data_quality"] == 0.9, "Should take the max value for data_quality"
    assert combined_scores["source_reliability"] == 0.8, "Should keep state1's value"
    assert combined_scores["data_completeness"] == 0.6, "Should add state2's unique key"
    assert len(combined_scores) == 3, "Should have 3 keys in total"

def test_iteration_count_reducer():
    """Test the iteration count reducer."""
    state1 = AgentState(prompt="Test prompt", iteration_count=2)
    state2 = AgentState(prompt="Test prompt", iteration_count=3)
    
    combined_count = reduce_iteration_count(state1, state2)
    
    assert combined_count == 5, "Should add the iteration counts"

def test_utility_function():
    """Test the create_initial_state utility function."""
    # Test country mode
    state = create_initial_state(mode_name="emissions", which_name="TestSector", country_name="TestCountry")
    assert state.target_country == "TestCountry"
    assert state.target_which == "TestSector"
    assert state.prompt == "CCRA Mode: emissions, Type: TestSector, Country: TestCountry"
    assert state.research_mode == "country"
    assert state.target_city is None

def test_utility_function_city_mode():
    """Test the create_initial_state utility function for city mode."""
    state = create_initial_state(mode_name="hazards", which_name="heatwave", city_name="TestCity")
    assert state.target_city == "TestCity"
    assert state.target_country is None
    assert state.target_which == "heatwave"
    assert state.prompt == "CCRA Mode: hazards, Type: heatwave, City: TestCity"
    assert state.research_mode == "city"
    
def test_utility_function_validation():
    """Test that create_initial_state validates input combinations."""
    # Test mixed mode rejection
    try:
        create_initial_state(mode_name="emissions", which_name="TestSector", city_name="TestCity", country_name="TestCountry")
        assert False, "Should have raised ValueError for mixed modes"
    except ValueError as e:
        assert "Cannot specify both city_name and country_name" in str(e)
    
    # Test missing parameters rejection
    try:
        create_initial_state(mode_name="hazards", which_name="heatwave")
        assert False, "Should have raised ValueError for missing parameters"
    except ValueError as e:
        assert "Must specify either city_name OR both country_name and sector_name" in str(e)
    
    # Test incomplete country mode
    try:
        create_initial_state(mode_name="hazards", which_name="heatwave", country_name="TestCountry")
        assert False, "Should have raised ValueError for incomplete country mode"
    except ValueError as e:
        assert "Must specify either city_name OR both country_name and sector_name" in str(e)

def test_serialization():
    """Test that we can serialize the state to JSON."""
    state = create_initial_state(mode_name="emissions", which_name="TestSerializeSector", country_name="TestSerializeCountry")
    try:
        json_state = json.dumps(asdict(state))
        # Test deserialization
        restored_dict = json.loads(json_state)
        assert restored_dict["prompt"] == state.prompt, "Prompt should match after serialization"
    except Exception as e:
        pytest.fail(f"Serialization failed: {e}")

if __name__ == "__main__":
    print("Running AgentState tests directly...")
    pytest.main(["-xvs", __file__]) 