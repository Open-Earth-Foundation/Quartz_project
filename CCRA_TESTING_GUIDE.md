# 🧪 CCRA Dataset Discovery Agent - Testing & Usage Guide

## 🚀 Quick Start Testing

### Prerequisites

```bash
# 1. Activate virtual environment
.venv\Scripts\activate

# 2. Ensure API keys are set in .env file
# OPENROUTER_API_KEY=your_openrouter_key_here
# GOOGLE_API_KEY=your_google_api_key_here
# GOOGLE_CSE_ID=your_custom_search_engine_id
```

### Basic Test Commands

```bash
# Test 1: Heatwave hazards for Germany (uses specific hazards_heatwave.md prompt)
python main.py --mode hazards --which heatwave --country Germany --max-iterations 1

# Test 2: Building exposure globally (uses generic ccra_planner.md prompt)
python main.py --mode exposure --which buildings --max-iterations 1

# Test 3: Socioeconomic vulnerability for France (uses specific vulnerability_socioeconomic.md prompt)
python main.py --mode vulnerability --which socioeconomic --country France --max-iterations 1

# Test 4: City-specific flood hazards
python main.py --mode hazards --which flood --city "New York" --max-iterations 1

# Test 5: View all available options
python main.py --help
```

## 📝 Current Prompt Structure Explained

### **Prompt File Organization**

The system uses different prompt templates based on your CCRA query:

#### ✅ **Active CCRA Prompts** (Currently Used)

```
agents/prompts/
├── ccra_planner.md           # Generic CCRA planner (fallback)
├── ccra_reviewer.md          # CCRA-focused content reviewer
├── hazards_heatwave.md       # Specific: Heatwave hazard datasets
├── exposure.md               # Comprehensive exposure indicators
├── vulnerability_socioeconomic.md  # Specific: Socioeconomic vulnerability
└── extractor_prompt.md       # Data extraction template
```

#### ❌ **Legacy GHGI Prompts** (Should be cleaned up)

```
agents/prompts/
├── afolu.md, ippu.md, waste.md, etc.  # Old GHGI sector prompts
├── agent1_planner.md         # Old GHGI planner
├── agent4_reviewer.md        # Old GHGI reviewer (replaced by ccra_reviewer.md)
└── *_city.md files           # Old GHGI city-specific prompts
```

### **How Prompt Selection Works**

1. **Specific Prompts First**: System looks for `{mode}_{type}.md`

   - `--mode hazards --which heatwave` → `hazards_heatwave.md` ✅
   - `--mode exposure --which comprehensive` → `exposure.md` ✅
   - `--mode vulnerability --which socioeconomic` → `vulnerability_socioeconomic.md` ✅

2. **Generic Fallback**: If specific prompt doesn't exist
   - `--mode hazards --which drought` → `ccra_planner.md` (generic)
   - `--mode exposure --which people` → `ccra_planner.md` (generic)

### **Prompt Template Variables**

Each prompt uses placeholder variables that get replaced with your query context:

```markdown
**CCRA Mode:** {ccra_mode_from_AgentState} # "hazards"
**CCRA Type:** {ccra_type_from_AgentState} # "heatwave"  
**Geographic Scope:** {geographic_scope_from_AgentState} # "Country"
**Target Location:** {target_location_from_AgentState} # "Germany"
```

## 🧹 Recommended Cleanup Actions

### **Step 1: Remove Old GHGI Prompts**

```bash
# Navigate to prompts directory
cd agents/prompts

# Remove old GHGI sector prompts (keep as backup first)
mkdir ../backup_old_prompts
mv afolu*.md ippu*.md waste*.md transportation*.md stationary_energy*.md ../backup_old_prompts/
mv agent1_planner*.md agent4_reviewer.md ../backup_old_prompts/
```

### **Step 2: Create Missing CCRA Prompts**

You should create specific prompts for commonly used combinations:

```bash
# Priority prompts to create:
# hazards_flood.md
# hazards_drought.md
# exposure_people.md
# exposure_infrastructure.md
# vulnerability_health.md
```

### **Step 3: Standardize Naming Convention**

Current naming is consistent: `{mode}_{type}.md`

## 🔍 What to Look for During Testing

### **✅ Success Indicators**

```
2025-XX-XX XX:XX:XX - INFO - agents.planner - Using specific CCRA prompt: hazards_heatwave.md
2025-XX-XX XX:XX:XX - INFO - agents.planner - CCRA Mode: hazards, Type: heatwave, Target Location: Germany
2025-XX-XX XX:XX:XX - INFO - agents.researcher - Processing search query: 'heatwave temperature extremes Germany'
2025-XX-XX XX:XX:XX - INFO - agents.researcher - Google search successful. Results: 10
```

### **❌ Error Indicators**

```
# Model not found errors (need to update model names in settings.toml)
Error code: 404 - No endpoints found for google/gemini-2.5-flash-preview

# Missing prompt files
Planner prompt file not found: hazards_drought.md

# API key issues
OpenRouter API key not configured
```

## 🛠️ Troubleshooting Common Issues

### **Issue 1: Model Not Found (404 Errors)**

**Problem**: `google/gemini-2.5-flash-preview-05-20` not available
**Solution**: Update `settings.toml`:

```toml
[models]
thinking_model = "deepseek/deepseek-r1-0528:free"
structured_model = "openai/gpt-4o-mini"  # Change this
relevance_check_model = "openai/gpt-4o-mini"  # Change this
```

### **Issue 2: Missing Specific Prompts**

**Problem**: `hazards_drought.md` doesn't exist
**Solution**: System falls back to `ccra_planner.md` (generic)
**Action**: Create specific prompts for frequently used combinations

### **Issue 3: No Search Results**

**Problem**: Google API quota exceeded or invalid keys
**Solution**: Check `.env` file and API quotas

### **Issue 4: Empty Results**

**Problem**: Relevance checker filters out all URLs
**Solution**: Disable relevance checking temporarily:

```python
# In config.py or settings.toml
ENABLE_PRE_SCRAPE_RELEVANCE_CHECK = False
```

## 📊 Expected Test Results

### **Successful Test Output Structure**

```
--- CCRA Agent Run Summary ---
CCRA Mode:               hazards
Target Type:             heatwave
Target Country:          Germany
Research Scope:          Country-specific
Total Iterations:        1
Searches Conducted:      1
Structured Items Found:  X (depends on data availability)
```

### **Key Log Entries to Verify**

1. ✅ Correct prompt loading: `Using specific CCRA prompt: hazards_heatwave.md`
2. ✅ CCRA context maintained: `CCRA Mode: hazards, Type: heatwave`
3. ✅ Search queries generated: Climate-focused search terms
4. ✅ URLs discovered: Climate data sources found
5. ✅ Results saved: JSON file with CCRA metadata

## 🎯 Advanced Testing Scenarios

### **Test Different Geographic Scopes**

```bash
# Global scope (no location specified)
python main.py --mode hazards --which heatwave --max-iterations 1

# Country-specific
python main.py --mode hazards --which heatwave --country "United Kingdom" --max-iterations 1

# City-specific
python main.py --mode exposure --which buildings --city "London" --max-iterations 1
```

### **Test All CCRA Modes**

```bash
# Test each mode with a common type
python main.py --mode hazards --which heatwave --country Germany --max-iterations 1
python main.py --mode exposure --which buildings --country Germany --max-iterations 1
python main.py --mode vulnerability --which socioeconomic --country Germany --max-iterations 1
```

### **Test Prompt Fallback Behavior**

```bash
# This should use ccra_planner.md (generic) since hazards_drought.md doesn't exist
python main.py --mode hazards --which drought --country Spain --max-iterations 1
```

## 📈 Performance Monitoring

### **Key Metrics to Track**

- **Prompt Loading**: Specific vs. generic prompt usage
- **Search Success**: Number of URLs found per query
- **Relevance Filtering**: URLs passing relevance check
- **Data Extraction**: Structured datasets discovered
- **Geographic Coverage**: Success rates by location type

### **Log Analysis Commands**

```bash
# Check which prompts are being used
grep "Using.*CCRA prompt" logs/ccra_agent_*.log

# Monitor search success rates
grep "Google search successful" logs/ccra_agent_*.log

# Track CCRA context maintenance
grep "CCRA Mode:" logs/ccra_agent_*.log
```

This guide should help you test the system thoroughly and understand how the prompt structure works!
