You are extracting structured information about a potential greenhouse gas inventory (GHGI) dataset.
The data source is relevant to the country: {target_country_or_unknown}.

DOCUMENT SOURCE URL: {url}

CONTENT TO ANALYZE:
```
{content}
```

GHGI SECTORS INFORMATION (Use for context):
```
{ghgi_sectors_info}
```

Please extract information based on the CONTENT TO ANALYZE and return it ONLY as a valid JSON object.
The JSON object must conform to a schema with these fields (definitions are for your guidance, especially if not operating in a strict schema-enforced mode):
{prompt_fields_description}

Specific instructions:
- For the 'name' field, identify the most specific name of the dataset or report from the CONTENT TO ANALYZE.
- For 'method_of_access', describe how the data can be accessed (e.g., if the content mentions downloadable files, an API, or if it appears to be a web query interface).
- For 'sector' and 'subsector', use the GHGI SECTORS INFORMATION for context, based on the CONTENT TO ANALYZE.
- sectors - afolu, ippu, waste, stationary_energy, transportation
- 'data_format' refers to the format of the actual data if mentioned or implied in the CONTENT TO ANALYZE (e.g., Excel, CSV, a specific table format).
- 'description' should be a concise summary of the dataset's content as found in CONTENT TO ANALYZE, including its provider, time period covered, and update frequency if mentioned.
- 'granularity' refers to geographic specificity mentioned in CONTENT TO ANALYZE (e.g., national, regional, municipal for {target_country_or_unknown}).

Output ONLY the JSON object.
- Adhere strictly to the schema if one is enforced by the system.
- For fields where information cannot be determined from the CONTENT TO ANALYZE, use null or omit the field if the schema allows (typically, use null for optional fields).
- Do NOT add any explanations, commentary, greetings, or any text whatsoever before or after the JSON object itself.
- Your entire response must be the JSON object and nothing else.
Ensure the output is a single, valid JSON object. 