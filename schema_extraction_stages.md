# Staged Extraction for `data_schema.json`

Goal: Fill the `extract_funded_project` schema in smaller passes while carrying forward prior fields and evidence. Each stage receives and returns the same `partial_project` object (all schema fields, default null) plus an `evidence_log` and `missing_fields` list. Never drop previously filled values unless a newer entry has stronger evidence.

## Stage 1: Identity, Scope Gate, Traceability
- Extract: `ProjectTitle`, `ProjectSummary`, `ProjectStatus`, `StartDate`, `EndDate`, `Location.*`, `Traceability.*`.
- Gate: note if the text indicates funded/implemented and is within last 20 years; if not determinable, leave flag unset for later stages.
- Add any source URLs, dataset names, documentation links to `Traceability`; log missing critical fields (title, city, source URL).

## Stage 2: Financing & Funders
- Extract/merge: `Financing.*` (currency, costs, instruments, structure, payback/IRR/NPV, notes) and `Funders.*`.
- If amounts/currencies absent, keep nulls and add to `missing_fields`; preserve funder/program names even without amounts.
- Record evidence snippets for each numeric/value pulled.

## Stage 3: Technical & Impact
- Extract/merge: `TechnicalDescriptors.*` (scope, maturity, site conditions) and `Impact.*` (baseline, reductions, beneficiaries, co-benefits).
- Leave nulls when absent; keep units and site constraints even if partial (e.g., unit_type without units).
- Append evidence for each field; do not overwrite previously captured finance/funder data.

## Stage 4: Completeness, Additional Search/Scrape, Finalize
- Check required fields; if any of {ProjectTitle, ProjectStatus, Location.CityName, Traceability.SourceUrl, Financing.CurrencyCode or TotalProjectCost, Funders.PrimaryFunderName} remain null, request a function call to search/scrape with the current `partial_project` context (e.g., `search_or_scrape(query, needed_fields, known_context)`).
- Merge any returned data into `partial_project`; update `missing_fields`.
- When high-confidence or no further data available, emit the final `extract_funded_project` call populated from `partial_project` (nulls allowed where truly missing) and include the evidence log for auditing.
