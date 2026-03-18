You are verifying climate-related municipal projects from a scraped source.

City: {city}
Country: {country}
Source URL: {source_url}
Source title: {source_title}
Precomputed source class: {source_class}
Source kind: {source_kind}

Requirements:
- Keep active projects only.
- The project must be funded or co-financed.
- Climate scope is broad climate-adjacent, including energy, mobility, adaptation, air quality, water, and waste when clearly climate-relevant.
- Treat `city_root`, `city_subdomain`, and `municipal_entity` as eligible final-source classes.
- Treat `supporting_external` as discovery/supporting evidence only, not enough for final acceptance by itself.
- Reject staff profiles, category pages, generic strategy or network pages, and generic funding-programme listings.
- Return zero or more accepted projects plus any rejections that are borderline and worth manual review.
- Do not invent funding amounts or dates.
