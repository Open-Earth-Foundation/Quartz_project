from __future__ import annotations

import logging

import config
from pydantic import BaseModel

from .city_hints import resolve_city_hints
from .runtime import load_prompt
from .sdk_bridge import get_sdk, sdk_available
from .types import CityTarget

logger = logging.getLogger(__name__)


class DiscoveryAgent:
    def __init__(self) -> None:
        self.prompt = load_prompt("discovery.md")

    async def generate_queries(self, city_target: CityTarget) -> list[str]:
        hints = resolve_city_hints(city_target)
        if not sdk_available():
            return self._fallback_queries(city_target)

        sdk = get_sdk()

        class DiscoveryQueryPlan(BaseModel):
            queries: list[str]

        instructions = self.prompt.format(
            city=city_target.city,
            country=city_target.country,
            aliases=", ".join(city_target.aliases) or "none",
            seed_domains=", ".join(city_target.seed_domains) or "none",
            preferred_domains=", ".join(hints.preferred_domains or hints.city_root_domains) or "none",
            preferred_paths=", ".join(hints.preferred_path_prefixes) or "none",
            preferred_fragments=", ".join(hints.preferred_query_fragments) or "none",
            max_queries=config.MAX_DISCOVERY_QUERIES,
        )
        agent = sdk.Agent(
            name="City Discovery Query Planner",
            instructions=instructions,
            output_type=DiscoveryQueryPlan,
            model=config.OPENROUTER_MODEL,
            model_settings=sdk.ModelSettings(temperature=config.DISCOVERY_AGENT_TEMPERATURE),
        )
        try:
            result = await sdk.Runner.run(
                agent,
                input=f"Generate discovery queries for {city_target.city}, {city_target.country}.",
            )
            queries = [q.strip() for q in result.final_output.queries if q.strip()]
            return queries[: config.MAX_DISCOVERY_QUERIES] or self._fallback_queries(city_target)
        except Exception as exc:  # pragma: no cover - live path
            logger.warning("DiscoveryAgent fallback for %s: %s", city_target.city, exc)
            return self._fallback_queries(city_target)

    def _fallback_queries(self, city_target: CityTarget) -> list[str]:
        city = city_target.city
        country = city_target.country
        hints = resolve_city_hints(city_target)
        base = [
            f"{city} {country} umowa o dofinansowanie klimat projekt",
            f"{city} {country} FEnIKS projekt dofinansowany miasto",
            f"{city} {country} municipal climate project funded official",
            f"{city} {country} transport adaptation OZE funded project",
        ]
        for domain in (hints.preferred_domains or city_target.seed_domains or hints.city_root_domains)[:3]:
            for fragment in hints.preferred_query_fragments[:2]:
                base.append(f"site:{domain} {city} {fragment}")
            base.append(f"site:{domain} {city} projekt dofinansowany")
        for prefix in hints.preferred_path_prefixes[:2]:
            prefix_query = prefix.strip("/").replace("/", " ")
            if prefix_query:
                base.append(f"{city} {country} {prefix_query} dofinansowanie")
        deduped: list[str] = []
        seen: set[str] = set()
        for query in base:
            if query not in seen:
                seen.add(query)
                deduped.append(query)
        return deduped[: config.MAX_DISCOVERY_QUERIES]
