# Knowledge Base: Funded City Climate Projects (Last 20 Years)

Use this as the canonical list of sources and access notes for finding funded or implemented city climate projects.

## Source Inventory (ranked buckets)
- City budget/finance portals: capital plans, bond issuances, grant awards, council minutes.
- Public works / procurement portals: project awards, RFP results, contract summaries.
- Grants & climate funds: national/subnational grant portals, green funds, resilience programs.
- Bonds & debt filings: muni bond offering docs, EMMA/SEDAR/SEDI equivalents, sustainability bond reports.
- Multilateral/IFI & foundations: World Bank/IDB/AFD/KfW projects, philanthropic climate grants.
- Networks & datasets: ICLEI, C40, CDP cities, OECD subnational finance, open data portals.

## Access Notes
- Prefer CSV/JSON endpoints when available; otherwise capture HTML/PDF URL and download date.
- Record funding authority (city/state/federal/foundation/multilateral) and source URL on ingest.
- Keep currency as-published; note currency code and any inflation/FX assumptions separately.

## Implementation Pointers
- Place new fetchers/scrapers under `bin/` or `agents/` per source.
- Store source URL and funding authority alongside each record to support traceability.
- Tag ingestion outputs with decision/approval dates to support the 20-year filter.
- Allow manual overrides for funding_status/implementation_status in `knowledge_base/` JSON/CSV helpers if heuristics are insufficient.
