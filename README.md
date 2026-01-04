# Quartz City Climate Projects Finder

LangGraph-powered agents to surface city climate projects that were funded or fully implemented in the last 20 years. Extraction is staged to stay token-efficient while filling the `extract_funded_project` schema and enforcing the default 20-year gate.

## Scope & Defaults
- Goal: use Quartz to find funded/implemented city climate projects within a rolling 20-year window.
- Gate first: title, city/region/country, status, start/end dates, source URL, funded/implemented flag.
- Configurable: `settings.toml` → `funding_scope.lookback_years` (default 20) and `funding_scope.accepted_statuses` (default: approved, in_implementation, completed, funded). Override via `--lookback-years` CLI.
- Shared rule text (for prompts/agents): see `agents/funding_scope.py::FUNDING_RULE_TEXT`.
- Export funded output: `--export-funded-report` writes CSV/JSON to `runs/funded_reports` with project summary, city, funding source/amount, dates, evidence URL.

## Staged Extraction
- Stage 1 (gate): lightweight extraction + in-scope check (funded/implemented + within lookback). If not in-scope, stop.
- Stage 2: financing/funders.
- Stage 3: technical/impact.
- Stage 4: gap check; trigger search/scrape function calls for missing critical fields; emit final `extract_funded_project` with evidence.
- Implementation: `agents/staged_project_extractor.py` orchestrates stages; `agents/funding_filter.py` enforces the funded/date gate before review; `agents/search_or_scrape.py` builds follow-up queries.
- Details: `schema_extraction_stages.md`.

## Project Structure
- `agents/` – agent nodes, prompts, and funding scope helpers (`funding_scope.py`, `staged_project_extractor.py`, `funding_filter.py`).
- `agent_state.py` – shared state dataclass.
- `config.py` / `settings.toml` – configuration and funding scope defaults.
- `data_schema.json` – `extract_funded_project` function schema.
- `implementation_plan.md` – work plan and tickets.
- `runs/`, `logs/`, `tests/` – outputs, logs, and test suites.

## Running Tests
```bash
python -m pytest tests/test_smoke.py -q
# or all tests
python -m pytest
```

## Configuration
1) `.env` for API keys.  
2) `settings.toml` for lookback years, accepted statuses, models, and search limits.  
3) `config.py` reads `settings.toml` and exposes shared constants.  
4) CLI overrides: `--lookback-years` to adjust funded filter; `--export-funded-report` to emit CSV/JSON; `--all-sectors` to run all sector prompts sequentially (country/region modes).

## Runbook (funded projects)
- Run researcher/agent: `python main.py --city "Paris" --sector stationary_energy --lookback-years 20`
- Export funded outputs: add `--export-funded-report`
- Rebuild vector exports/index: `python bin/reindex_vectors.py` (writes `logs/index_rebuild.json`)
- Insert to Supabase: `python insert_data_to_supabase.py --country "France"`
- Automation: schedule `bin/reindex_vectors.py` and `insert_data_to_supabase.py` via cron/GitHub Action after each ingestion run.
