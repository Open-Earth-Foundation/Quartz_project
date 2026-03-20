from __future__ import annotations

import logging

import config
from pydantic import BaseModel

from .city_hints import resolve_city_hints
from .runtime import load_prompt
from .sdk_bridge import get_sdk, sdk_available
from .types import CityTarget, DiscoveryQuery

logger = logging.getLogger(__name__)


class DiscoveryAgent:
    def __init__(self) -> None:
        self.prompt = load_prompt("discovery.md")

    async def generate_queries(self, city_target: CityTarget) -> list[DiscoveryQuery]:
        hints = resolve_city_hints(city_target)
        if not sdk_available():
            return self._fallback_queries(city_target)

        sdk = get_sdk()

        class DiscoveryQueryPlan(BaseModel):
            queries: list[DiscoveryQuery]

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
            queries = [
                DiscoveryQuery(query=item.query.strip(), scope=item.scope)
                for item in result.final_output.queries
                if item.query.strip()
            ]
            normalized = self._normalize_queries(queries, city_target)
            if len(normalized) < config.MAX_DISCOVERY_QUERIES:
                normalized = self._merge_queries(normalized + self._fallback_queries(city_target))
            return normalized[: config.MAX_DISCOVERY_QUERIES] or self._fallback_queries(city_target)
        except Exception as exc:  # pragma: no cover - live path
            logger.warning("DiscoveryAgent fallback for %s: %s", city_target.city, exc)
            return self._fallback_queries(city_target)

    def _fallback_queries(self, city_target: CityTarget) -> list[DiscoveryQuery]:
        city = city_target.city
        country = city_target.country
        hints = resolve_city_hints(city_target)
        domains = self._domain_candidates(hints, city_target)[:3]
        fragments = hints.preferred_query_fragments[:4] or ["climate project", "funded project", "mobility", "adaptation"]
        base = [
            DiscoveryQuery(query=f"{city} {country} municipal climate project funded official", scope="exploratory"),
            DiscoveryQuery(query=f"{city} {country} adaptation mobility energy funded project", scope="exploratory"),
        ]

        for index, domain in enumerate(domains):
            fragment = fragments[index % len(fragments)]
            base.append(DiscoveryQuery(query=f"site:{domain} {city} {fragment}", scope="bounded"))

        for prefix in hints.preferred_path_prefixes[:2]:
            prefix_query = prefix.strip("/").replace("/", " ")
            site_domain = domains[0] if domains else ""
            if prefix_query and site_domain:
                base.append(DiscoveryQuery(query=f"site:{site_domain} {city} {prefix_query} dofinansowanie", scope="bounded"))

        if city_target.country.casefold() == "poland":
            base.append(DiscoveryQuery(query=f"{city} {country} umowa o dofinansowanie klimat projekt", scope="bounded"))
        elif domains:
            base.append(DiscoveryQuery(query=f"site:{domains[0]} {city} funded climate project", scope="bounded"))
        else:
            base.append(DiscoveryQuery(query=f"{city} {country} funded climate project official", scope="bounded"))

        fallback_fragments = ["funded project", "climate", "mobility", "adaptation", "energy"]
        for domain in domains:
            for fragment in fallback_fragments:
                base.append(DiscoveryQuery(query=f"site:{domain} {city} {fragment}", scope="bounded"))

        return self._normalize_queries(self._merge_queries(base), city_target)

    def _domain_candidates(self, hints, city_target: CityTarget) -> list[str]:
        domains: list[str] = []
        seen: set[str] = set()
        for domain in [*hints.city_root_domains, *hints.preferred_domains, *city_target.seed_domains]:
            normalized = domain.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            domains.append(normalized)
        return domains

    def _normalize_queries(self, queries: list[DiscoveryQuery], city_target: CityTarget) -> list[DiscoveryQuery]:
        exploratory = [item for item in queries if item.scope == "exploratory"]
        bounded = [item for item in queries if item.scope == "bounded"]

        fallback_exploratory = [
            DiscoveryQuery(query=f"{city_target.city} {city_target.country} municipal climate project funded official", scope="exploratory"),
            DiscoveryQuery(query=f"{city_target.city} {city_target.country} adaptation mobility energy funded project", scope="exploratory"),
        ]
        existing_exploratory = {item.query for item in exploratory}
        for item in fallback_exploratory:
            if len(exploratory) >= 2:
                break
            if item.query not in existing_exploratory:
                exploratory.append(item)
                existing_exploratory.add(item.query)

        ordered = exploratory[:2] + bounded
        return self._merge_queries(ordered)[: config.MAX_DISCOVERY_QUERIES]

    def _merge_queries(self, queries: list[DiscoveryQuery]) -> list[DiscoveryQuery]:
        deduped: list[DiscoveryQuery] = []
        seen_queries: set[str] = set()
        for item in queries:
            key = item.query.strip()
            if not key or key in seen_queries:
                continue
            seen_queries.add(key)
            deduped.append(item)
        return deduped
