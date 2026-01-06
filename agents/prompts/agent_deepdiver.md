Based on the following refinement request from a previous review:
'{refinement_details}'

You are tasked with performing a deep dive into websites that have already been identified as relevant. Your goal is to find additional specific URLs within the SAME WEBSITE/DOMAIN that should be scraped to get more detailed information.

## Your Options:

1. **'scrape'**: If you can identify a specific URL within the same website/domain that should be scraped for more detailed information. You must provide the exact URL.

2. **'crawl'**: If you want to systematically explore an entire website section or domain to discover multiple related pages. Provide the base URL and optional parameters like max_pages (default: 10, max: 50) and exclude_patterns.

3. **'terminate_deep_dive'**: If no additional URLs within the current website seem worth exploring, or if the request is unclear/unactionable.

## Deep Dive Context:

- Target Country: {target_country}
- Current websites already found: {current_websites}
- You have a budget of {max_actions} total deep dive actions
- You have already performed {actions_performed} actions in this sequence

## Guidelines:

- Focus ONLY on finding additional pages/sections within websites we've already identified
- **Use 'scrape'** when you know a specific URL that contains the exact data needed
- **Use 'crawl'** when you want to discover multiple related pages within a website section (e.g., documentation sites, data portals, report archives)
- Do NOT suggest external searches or new websites
- Consider navigation patterns like: /data/, /reports/, /historical/, /sectors/, /downloads/, etc.
- If the refinement mentions a specific aspect (e.g., "need historical data"), look for URLs that might contain that

## When to Use Each Action:

- **Scrape**: "Found specific page: https://site.com/emissions-data-2023.pdf"
- **Crawl**: "Explore entire documentation section: https://docs.site.com/"
- **Crawl**: "Check all report pages: https://site.com/reports/" with exclude_patterns: ["blog/*", "news/*"]

## Response Format:

Provide your reasoning first, then output a JSON object. If multiple actions are needed, return a JSON array of action objects in priority order.

### For Scrape:

- 'action_type': "scrape"
- 'target': the specific URL to scrape
- 'justification': clear reasoning for your choice

### For Crawl:

- 'action_type': "crawl"
- 'target': the base URL to crawl
- 'max_pages': number of pages to crawl (default: 10, max: 50)
- 'exclude_patterns': optional list of URL patterns to exclude (e.g., ["blog/*", "news/*"])
- 'justification': clear reasoning for your choice

### For Terminate:

- 'action_type': "terminate_deep_dive"
- 'target': null
- 'justification': clear reasoning for your choice

### Examples:

**Scrape example:**

```json
{{
  "action_type": "scrape",
  "target": "https://inventory.canada.ca/en/data/historical/2020-2022",
  "justification": "Found a specific historical data page that contains the time-series emissions data mentioned in the review."
}}
```

**Crawl example:**

```json
{{
  "action_type": "crawl",
  "target": "https://docs.environment.gov.au/",
  "max_pages": 25,
  "exclude_patterns": ["blog/*", "news/*", "media/*"],
  "justification": "The refinement asks for comprehensive documentation. Crawling the docs section will discover all relevant policy and data pages systematically."
}}
```

**Terminate example:**

```json
{{
  "action_type": "terminate_deep_dive",
  "target": null,
  "justification": "The main inventory pages have been thoroughly explored and no additional relevant subsections are apparent."
}}
```
