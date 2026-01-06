You are extracting information about **funded or implemented climate projects** (not GHGI datasets).
The project source is relevant to the country: {target_country_or_unknown}.

DOCUMENT SOURCE URL: {url}

CONTENT TO ANALYZE:

```
{content}
```

Please extract information based on the CONTENT TO ANALYZE and return it ONLY as a valid JSON object.
The JSON object must conform to a schema with these fields:
{prompt_fields_description}

Specific instructions for funded project extraction:

- For the 'name' field, identify the **project name or title** from the CONTENT TO ANALYZE (e.g., "Solar Energy Initiative", "Bus Rapid Transit Project", "Green Building Program").
- For 'method_of_access', describe how you found information about this project (e.g., from news article, government announcement, development bank document, project website).
- For 'sector', use climate/project context: afolu (agricultural/forestry projects), ippu (industrial projects), waste (waste management), stationary_energy (energy/building), transportation (mobility).
- For 'subsector', identify specific project type (e.g., "Solar Installation", "Bus Fleet", "Landfill Gas", "Reforestation").
- For 'data_format', note where you found the information (e.g., "web announcement", "PDF document", "news article", "government portal").
- For 'description', extract: (1) what the project does, (2) location/city if mentioned, (3) funding source/amount if mentioned, (4) implementation status if mentioned (e.g., "approved", "construction started", "completed").
- For 'granularity', note if project is municipal/city-level, regional, or national.

CRITICAL: You are looking for PROJECTS, not datasets or reports. Look for:

- Project names (not data portal names)
- Implementation status (approved, funded, started, under construction, completed)
- Funding sources (World Bank, Green Climate Fund, government budget, private investment)
- City/region location
- Any amounts/funding figures

Output ONLY the JSON object.

- Adhere strictly to the schema if one is enforced by the system.
- For fields where information cannot be determined from the CONTENT TO ANALYZE, use null.
- Do NOT add any explanations, commentary, greetings, or any text whatsoever before or after the JSON object itself.
- Your entire response must be the JSON object and nothing else.
  Ensure the output is a single, valid JSON object.
