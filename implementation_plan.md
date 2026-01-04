# Rework Plan: Quartz for Funded City Climate Projects (Last 20 Years)

## Scope & Success Criteria
- [x] Update `README.md` and `config.py` goal statements to: "Use Quartz to find city climate projects that were funded or fully implemented in the last 20 years."
- [x] Define "funded" rule set in code (has municipal/3rd-party funding or marked implemented) and make a single constant shared by agents/prompts.
- [x] Add default date window filter (>= current_year - 20) surfaced in CLI/config flags and documented in `README.md`.

## Data Sources & Acquisition
- [x] Inventory and rank data sources for funded city climate projects (city budget portals, grants, bonds, public works, OECD/ICLEI datasets); capture in `knowledge_base/README` with access steps.
- [x] Add/adjust fetchers to pull structured data from chosen sources; place scripts in `bin/` or `agents/` as appropriate.
- [x] Ensure ingest jobs store source URLs and funding authority (city, state, federal, foundation, multilateral).

## Schema & Storage
- [x] Extend record schema with: project_name, city/region/country, sector, funding_status (funded/implemented), funding_amount + currency, funding_source, approval_date, implementation_status, timeline_start/end, evidence_snippet, source_url.
- [x] Update Supabase/DB DDL and `insert_data_to_supabase.py` to reflect schema; add migrations/backfill for existing rows.
- [x] Normalize currency/date handling (including inflation-note field) and add unique keys to avoid duplicates.

## Staged Extraction (data_schema.json)
- [x] Adopt 4-pass extraction flow from `schema_extraction_stages.md` for `extract_funded_project`: Stage 1 (identity/traceability), Stage 2 (financing/funders), Stage 3 (technical/impact), Stage 4 (gap check + search/scrape).
- [x] Make Stage 1 a lightweight “gate” to minimize tokens: only pull {ProjectTitle, Location (city/region/country), ProjectStatus, StartDate, EndDate, Traceability.SourceUrl} and a yes/no/unknown funded/implemented flag; proceed to later stages only if funded + within 20 years is likely.
- [x] Implement shared `partial_project` + `evidence_log` state across stages; never drop previously filled values unless superseded with stronger evidence.
- [x] Add function/tooling for `search_or_scrape(query, needed_fields, known_context)` so Stage 4 can request follow-up searches to close required fields.
- [x] Update `agents/planner.py`, prompt templates, and agent graph to sequence these stages, pass forward context, and emit final `extract_funded_project` calls with nulls for truly missing fields.
- [x] Add tests/fixtures covering staged merges, evidence preservation, and function-call trigger when key fields (title, status, city, source URL, funder/amount) remain null.

## ETL & Normalization
- [x] Build parsers/normalizers per source to map into the unified schema; log unmapped fields for follow-up.
- [x] Add heuristics/classifier to tag funding_status and implementation_status from text; allow manual overrides in `knowledge_base/`.
- [x] Add dedupe step (project name + city + year) and QA checks with small golden set stored in `tests/data/`.

## Retrieval & Quartz Graph Updates
- [x] Update retrieval config to enforce date window and funding_status filters before embedding queries.
- [x] Adjust `create_agent_graph.py` and `agent_state.py` to include a funding filter node and evidence validation step.
- [x] Refresh vector indexing to include new fields (city, funding_amount, funding_source) and rerun indexing job.

## Prompting & Interaction
- [x] Rewrite system/user prompts to restate the funded-20-year scope and require citing funding evidence (source + amount/authority if present).
- [x] Add response template that surfaces: project summary, city, funding source, amount, decision/implementation date, evidence snippet + URL.
- [x] Update fallback/clarification prompts to ask for city/region or year bounds when missing.

## Testing & Evaluation
- [x] Create test queries covering funded vs unfunded, older-than-20 years, and multiple cities; add to `tests/`.
- [x] Add unit tests for funding classifiers/filters and date window logic; wire into `pytest` and `run_tests.py`.
- [x] Define evaluation checklist/metrics (precision on funded filter, citation rate, recall on sample set) and log results in `logs/`.

## Observability & Output
- [x] Enhance logging to show how many candidates are dropped by funding/date filters and why; include sample evidence.
- [x] Add export/report option (CSV/JSON) with required fields for downstream analysis.
- [x] Track ingestion freshness and source coverage in `README.md`/status doc.

## Ops & Configuration
- [x] Review `.env` for needed API keys/endpoints for new sources; update `.env.example`.
- [x] Document runbook for data refresh and Quartz pipeline execution in `README.md` and `knowledge_base/README`.
- [x] Ensure automation scripts (cron/GitHub Action) target new ingestion and reindex steps.
