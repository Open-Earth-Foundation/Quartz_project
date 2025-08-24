# LangGraph-Powered CCRA Dataset Discovery Agent

A sophisticated multi-agent system for discovering and retrieving Climate Change Risk Assessment (CCRA) datasets from global sources. The system specializes in finding hazard, exposure, and vulnerability datasets for climate risk analysis.

## Overview

This agent system helps researchers and practitioners discover climate risk assessment datasets by:

- **Hazards**: Climate events and phenomena (heatwaves, floods, droughts, landslides)
- **Exposure**: Assets and systems at risk (people, buildings, infrastructure, agriculture, economy)
- **Vulnerability**: Susceptibility factors (socioeconomic conditions)

The system uses a multi-agent architecture with specialized agents for planning, research, review, extraction, and deep-dive analysis.

### Current Implementation Status

| Mode              | Status                   | Available Types | Implementation                               |
| ----------------- | ------------------------ | --------------- | -------------------------------------------- |
| **Hazards**       | ✅ Fully Implemented     | 4/4             | Individual prompts for each hazard type      |
| **Exposure**      | ✅ Implemented           | 5/5             | Unified prompt covering all exposure types   |
| **Vulnerability** | ⚠️ Partially Implemented | 1/5             | Only socioeconomic vulnerability implemented |

**✅ Fully Working**: 4 hazard types, 5 exposure types
**⚠️ Limited**: Only socioeconomic vulnerability
**❌ Not Available**: Health, access_to_services, environmental_buffers, governance vulnerability types

## What the System Can Do Now

### 🔍 **Hazard Discovery** (4 Types Available)

The system can discover comprehensive datasets for:

- **Heatwaves**: Temperature extremes, heat indices (HWMId, WBGT, UTCI), heat stress indicators, climate projections
- **Droughts**: Precipitation deficits, soil moisture, evapotranspiration, drought indices (SPI, SPEI, PDSI), water balance
- **Floods**: Precipitation intensity, hydrological factors, soil moisture, flood inundation, flood risk components
- **Landslides**: Geological factors, hydrological triggers, geotechnical properties, susceptibility mapping

Each hazard type has specialized search strategies, data format priorities, and geographic scope optimization.

### 📍 **Exposure Assessment** (5 Types Available)

Comprehensive exposure analysis covering:

- **People**: Population density, demographics, gridded population data
- **Buildings**: Built-up areas, urban extent, building footprints, impervious surfaces
- **Infrastructure**: Critical facilities, hospitals, schools, transportation networks
- **Agriculture**: Cropland, pasture, livestock, agricultural land use
- **Economy**: Property values, business activity, economic assets

Unified system covering 15+ exposure categories with geospatial focus.

### 🎯 **Vulnerability Analysis** (1 Type Available)

Currently focuses on socioeconomic vulnerability:

- **Socioeconomic**: Income distribution, education levels, employment patterns, housing conditions, social capital

## 🔮 **Future Development Roadmap**

### Planned Vulnerability Types

- **Health**: Disease burden, healthcare access, health infrastructure
- **Access to Services**: Utility access, transportation, communication networks
- **Environmental Buffers**: Natural protection, ecosystem services, biodiversity
- **Governance**: Institutional capacity, disaster response, policy frameworks

### Potential Enhancements

- **Additional Hazard Types**: Wildfire, coastal erosion, extreme precipitation
- **Type-specific Exposure Prompts**: Individual prompts for each exposure type
- **Multi-language Support**: Enhanced local language search capabilities
- **Real-time Data Integration**: Live monitoring and early warning systems
- **Risk Calculation**: Automated risk assessment combining H×E×V components

## Quick Start

### Basic Usage

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Search for heatwave hazard data in Germany
python main.py --mode hazards --which heatwave --country Germany

# Search for building exposure data in New York
python main.py --mode exposure --which buildings --city "New York"

# Search for socioeconomic vulnerability data globally
python main.py --mode vulnerability --which socioeconomic

# Use English-only sources
python main.py --mode hazards --which flood --country France --english

# Note: Only socioeconomic vulnerability is currently implemented
# Other vulnerability types (health, access_to_services, etc.) are planned but not yet available
```

### CCRA Modes and Types

**Hazards** (Climate events):

- `heatwave`, `drought`, `flood`, `landslide`

**Exposure** (Assets at risk):

- `people`, `buildings`, `infrastructure`, `agriculture`, `economy`

**Vulnerability** (Susceptibility factors):

- ✅ `socioeconomic` - Income, education, employment, housing conditions
- ❌ `health` - Not implemented
- ❌ `access_to_services` - Not implemented
- ❌ `environmental_buffers` - Not implemented
- ❌ `governance` - Not implemented

## Project Structure

```
Quartz_project/
├── .venv/                    # Python virtual environment
├── agents/                   # Multi-agent system components
│   ├── planner.py           # Query formulation & strategic planning
│   ├── researcher.py        # Search and data collection
│   ├── reviewer.py          # Content quality assessment
│   ├── extractor.py         # Structured data extraction
│   ├── deep_diver.py        # Deep analysis and follow-up
│   ├── schemas.py           # Data models and validation
│   └── prompts/             # CCRA-specific prompt templates
│       ├── hazards_drought.md      # Drought hazard discovery
│       ├── hazards_flood.md        # Flood hazard discovery
│       ├── hazards_heatwave.md     # Heatwave hazard discovery
│       ├── hazards_landslide.md    # Landslide hazard discovery
│       ├── exposure.md             # All exposure types (unified)
│       ├── vulnerability_socioeconomic.md  # Socioeconomic vulnerability
│       ├── ccra_planner.md         # Search planning
│       ├── ccra_reviewer.md        # Content review
│       └── extractor_prompt.md     # Data extraction
├── knowledge_base/          # CCRA framework and reference data
│   └── ccra_framework.md    # Comprehensive CCRA methodology
├── agent_state.py           # Core state management for LangGraph
├── config.py                # Configuration and environment variables
├── main.py                  # CLI interface and orchestration
├── requirements.txt         # Python dependencies
└── settings.toml            # Configuration settings
```

## Architecture

### Multi-Agent Workflow

1. **Planner Agent**: Generates CCRA-specific search strategies
2. **Researcher Agent**: Executes searches and collects climate data URLs
3. **Reviewer Agent**: Assesses content relevance and quality
4. **Extractor Agent**: Extracts structured CCRA metadata
5. **Deep Diver Agent**: Performs targeted follow-up searches

### State Management

The system uses a central `AgentState` dataclass that maintains:

- CCRA mode and type context
- Geographic scope (global, country, city)
- Search plans and discovered URLs
- Extracted climate dataset metadata
- Decision logs and confidence scores

## Configuration

### Environment Setup

1. **Create `.env` file** with API keys:

```bash
OPENROUTER_API_KEY=your_openrouter_key_here
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CSE_ID=your_custom_search_engine_id
```

2. **Install dependencies**:

```bash
pip install -r requirements.txt
```

3. **Configure settings** in `settings.toml`:

```toml
[general]
app_name = "CCRA Dataset Discovery Agent"
version = "2.0.0"

[models]
thinking_model = "deepseek/deepseek-r1-0528:free"
structured_model = "google/gemini-2.5-flash-preview-05-20"

[search]
max_results_per_query = 10
max_google_queries_per_run = 50
```

## CLI Reference

### Required Parameters

- `--mode`: CCRA component (`hazards`, `exposure`, `vulnerability`)
- `--which`: Specific type within the mode

### Optional Parameters

- `--country`: Target country for country-specific datasets
- `--city`: Target city for city-specific datasets
- `--english`: Use English-only search mode
- `--log-level`: Set logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `--max-iterations`: Override maximum iterations

### Examples

```bash
# Comprehensive heatwave analysis for Germany
python main.py --mode hazards --which heatwave --country Germany --log-level DEBUG

# Global drought hazard datasets
python main.py --mode hazards --which drought

# Urban building exposure in London
python main.py --mode exposure --which buildings --city London

# Note: Only socioeconomic vulnerability is currently available
# python main.py --mode vulnerability --which health --country Japan --english  # Not implemented

# Quick test run (1 iteration only)
python main.py --mode hazards --which flood --country Netherlands --max-iterations 1
```

## CCRA Framework

The system implements a comprehensive Climate Change Risk Assessment framework:

**Risk = Hazard × Exposure × Vulnerability**

### Hazards

Climate events and phenomena that can cause harm:

- **Temperature extremes**: Heatwaves, cold spells
- **Precipitation extremes**: Floods, droughts, extreme precipitation
- **Wind events**: Windstorms, tropical cyclones
- **Compound events**: Multi-hazard scenarios

### Exposure

Assets, systems, and populations at risk:

- **Human systems**: Population, communities, settlements
- **Built environment**: Buildings, infrastructure, transportation
- **Natural systems**: Ecosystems, agriculture, water resources
- **Economic systems**: GDP, economic activities, supply chains

### Vulnerability

Susceptibility and adaptive capacity factors:

- **Social vulnerability**: Demographics, income, education
- **Health vulnerability**: Disease burden, healthcare access
- **Institutional vulnerability**: Governance, planning capacity
- **Environmental vulnerability**: Ecosystem degradation, resource availability

## Output and Results

### Structured Data Schema

The system extracts climate datasets with standardized metadata:

```json
{
  "name": "European Heat Risk Atlas",
  "url": "https://example.com/heat-atlas",
  "ccra_mode": "hazards",
  "ccra_type": "heatwave",
  "spatial_resolution": "1km grid",
  "temporal_coverage": "1981-2020",
  "climate_scenario": "RCP4.5, RCP8.5",
  "data_format": "NetCDF",
  "description": "High-resolution heat stress indicators for Europe",
  "country": "Germany"
}
```

### Result Files

Results are saved in the `runs/` directory:

- `results_hazards_heatwave_Germany_YYYYMMDD_HHMMSS.json`
- Structured metadata for discovered datasets
- Decision logs and confidence scores
- Search strategies and URLs processed

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run unit tests only (no API calls)
python -m pytest -m "not integration"

# Run integration tests (requires API keys)
python -m pytest -m integration

# Test specific components
python -m pytest tests/test_planner.py
python -m pytest tests/test_researcher.py
```

### Test Categories

- **Unit tests**: Mock-based testing of agent logic
- **Integration tests**: Real API calls with safety limits
- **CLI tests**: Command-line interface validation
- **CCRA tests**: Framework-specific functionality

## Development

### Adding New CCRA Types

To implement missing vulnerability types or new hazard types:

1. **Create prompt template** in `agents/prompts/` (follow existing pattern)
2. **Update main.py** hazard_types/exposure_types/vulnerability_types lists
3. **Update README.md** to reflect new capabilities
4. **Add tests** in `tests/` directory

**Current Priority**: Implement missing vulnerability types (health, access_to_services, environmental_buffers, governance)

### Extending Geographic Scope

The system supports multiple geographic scopes:

- **Global**: Worldwide datasets and indicators
- **Country**: National-level climate data
- **City**: Urban-specific risk assessments

### Custom Models

Configure different LLM models in `settings.toml`:

- `thinking_model`: For reasoning and planning
- `structured_model`: For data extraction
- `relevance_check_model`: For content filtering

## Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure `.env` file contains valid keys
2. **Model Not Found**: Check model availability on OpenRouter
3. **No Results**: Try broader search terms or different geographic scope
4. **Rate Limits**: Reduce `max_google_queries_per_run` in settings

### Debug Mode

Enable detailed logging:

```bash
python main.py --mode hazards --which heatwave --country Germany --log-level DEBUG
```

### Log Files

Logs are saved in `logs/` directory:

- `ccra_agent_YYYYMMDD_HHMMSS.log`: Main application log
- `planner_outputs/`: LLM planning responses
- `researcher_outputs/`: Search and scraping results

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Citation

If you use this system in your research, please cite:

```bibtex
@software{ccra_discovery_agent,
  title={CCRA Dataset Discovery Agent},
  author={Climate Risk Research Team},
  year={2025},
  url={https://github.com/your-org/ccra-discovery-agent}
}
```
