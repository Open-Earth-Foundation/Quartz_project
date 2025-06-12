# LangGraph-Powered GHGI Dataset Discovery Agent

A sophisticated agent system for discovering and retrieving greenhouse gas inventory (GHGI) datasets from Polish government sources.

## Project Structure

```
automatic_research/
├── .venv/                    # Python virtual environment
├── knowledge_base/           # Static knowledge sources (data, prompts)
├── agent_state.py            # Core state management for LangGraph
├── config.py                 # Configuration and environment variables
├── implementation_plan.md    # Detailed project plan with tasks
├── requirements.txt          # Python dependencies
├── settings.toml             # Configuration settings
├── test_*.py                 # Various test scripts
```

## Current Implementation Status

- ✅ Environment setup with Python venv
- ✅ Configuration and API key management
- ✅ Basic smoke tests for all dependencies (Firecrawl, LangGraph, OpenRouter)
- ✅ AgentState definition with full fields and reducers
- ✅ Settings management via TOML file
- ✅ Researcher Agent with async search and prioritization of relevant domains
- ✅ Data Extraction Agent with PDF processing and structured data output
- ✅ Automated testing with pytest and mock objects

## Next Steps

1. Implement Agent 1 (Query Formulation & Strategic Planner)
2. Build knowledge base YAML of Polish data sources
3. Create prompt templates for agent interactions
4. Implement remaining agent (Reviewer)

## Running Tests

You can run all tests with a single command:

```bash
python run_tests.py
```

Or use pytest directly:

```bash
pytest tests/
```

Individual test files can also be run directly:

```bash
python tests/test_keys.py     # Test API key loading
python tests/test_firecrawl.py # Test Firecrawl integration
python tests/test_langgraph.py # Test LangGraph functionality
python tests/test_openrouter.py # Test OpenRouter/LLM access
python tests/test_state.py     # Test state management
```

## Configuration

Configuration is managed through:

1. `.env` file - API keys and credentials
2. `settings.toml` - Application settings
3. `config.py` - Runtime configuration management

## State Management

The agent system uses a central `AgentState` dataclass for maintaining context and information. This state is passed between agents and includes:

- User's original query (prompt)
- Search plans and strategies
- URLs discovered during research
- Document content and extracted data
- Decision logs and confidence scores

## Components

### Researcher Agent

The Researcher Agent (Phase 5) handles iterative research and retrieval:

- Performs broad searches based on the user's query
- Prioritizes promising sources (gov.pl domains, KOBIZE, etc.)
- Implements adaptive search strategies when initial results are poor
- Uses specialized scraping methods for JS-heavy pages and documents
- Enriches the agent state with discovered URLs and document content

### Data Extraction Agent

The Data Extraction Agent (Phase 6) processes and structures data:

- Extracts text from various document formats (PDF, HTML)
- Parses tables and structured data from documents
- Organizes information according to the GHGI sector schema
- Uses LLMs for intelligent extraction of key data points
- Produces standardized JSON outputs with consistent schema

## Testing

This project includes both unit tests (with mocks) and integration tests (with real API calls).

### Running Unit Tests

Unit tests use mocks and stubs to avoid external API calls:

```bash
# Run all unit tests (excluding integration tests)
python -m pytest -m "not integration"

# Run specific test files
python -m pytest tests/test_deep_diver.py -m "not integration"
python -m pytest tests/test_researcher.py -m "not integration"
```

### Running Integration Tests

Integration tests make real API calls with strict safety limits:

- **Crawl tests**: Limited to 2 pages maximum
- **Scrape tests**: Limited to 1 URL per test
- **Timeout**: 1 minute maximum per test

```bash
# Set required environment variables
export FIRECRAWL_API_KEY="your_key_here"  # Required for integration tests
export OPENROUTER_API_KEY="your_key_here"  # Required for LLM tests (optional for some)

# Run integration tests only
python -m pytest -m integration

# Run specific integration test
python -m pytest tests/test_deep_diver.py::test_deep_diver_real_crawl_safety_limits -m integration
```

**Integration Test Safety Features:**

- 🔒 **Hard limits**: Never exceeds 2 pages for crawl tests, 1 URL for scrape tests
- ⏱️ **Timeouts**: 1-minute maximum per crawl operation
- 🎯 **Safe targets**: Uses httpbin.org for testing (safe, lightweight)
- 🚫 **Exclusions**: Automatically excludes heavy sections (admin, docs, status endpoints)
- ⚡ **Quick skip**: Automatically skips if API keys not available

### Running All Tests

```bash
# Run everything (unit + integration)
python -m pytest

# Run with verbose output
python -m pytest -v

# Run with coverage
python -m pytest --cov=agents
```
