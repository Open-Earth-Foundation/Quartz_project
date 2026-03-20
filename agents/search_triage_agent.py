from __future__ import annotations

import config
from pydantic import BaseModel

from .runtime import load_prompt
from .sdk_bridge import get_sdk, sdk_available
from .search import CITY_ECOSYSTEM_CLASSES, normalize_domain
from .types import CityTarget, ScrapeDecision, SearchHit

PROJECT_KEYWORDS = (
    "project",
    "projekt",
    "funded",
    "funding",
    "dofinans",
    "grant",
    "adapt",
    "climate",
    "klimat",
    "mobility",
    "transport",
    "tram",
    "metro",
    "energy",
    "solar",
    "waste",
    "water",
    "retention",
    "feniks",
    "oze",
    "life",
)


class SearchTriageAgent:
    def __init__(self) -> None:
        self.prompt = load_prompt("search_triage.md")

    async def triage_hits(self, city_target: CityTarget, hits: list[SearchHit]) -> list[SearchHit]:
        for hit in hits:
            if hit.query_scope != "exploratory":
                hit.scrape_decision = "scrape"
                hit.scrape_reason = "bounded query"
            elif hit.source_class in CITY_ECOSYSTEM_CLASSES:
                hit.scrape_decision = "scrape"
                hit.scrape_reason = "exploratory hit is already in city ecosystem"

        candidates = [hit for hit in hits if hit.query_scope == "exploratory" and hit.scrape_decision is None]
        if not candidates:
            return hits

        allowed = candidates[: config.MAX_EXPLORATORY_TRIAGE_HITS]
        overflow = candidates[config.MAX_EXPLORATORY_TRIAGE_HITS :]
        for hit in overflow:
            hit.scrape_decision = "skip"
            hit.scrape_reason = "outside exploratory triage budget"

        if sdk_available():
            try:
                await self._triage_with_sdk(city_target, allowed)
            except Exception:
                self._triage_with_heuristics(city_target, allowed)
        else:
            self._triage_with_heuristics(city_target, allowed)
        return hits

    async def _triage_with_sdk(self, city_target: CityTarget, hits: list[SearchHit]) -> None:
        sdk = get_sdk()

        class HitDecision(BaseModel):
            url: str
            decision: ScrapeDecision
            reason: str

        class HitDecisionBatch(BaseModel):
            decisions: list[HitDecision]

        instructions = self.prompt.format(
            city=city_target.city,
            country=city_target.country,
            aliases=", ".join(city_target.aliases) or "none",
        )
        agent = sdk.Agent(
            name="Exploratory Search Triage",
            instructions=instructions,
            output_type=HitDecisionBatch,
            model=config.OPENROUTER_MODEL,
            model_settings=sdk.ModelSettings(temperature=0.0),
        )
        payload = "\n".join(
            f"- url={hit.url} | title={hit.title} | snippet={hit.snippet} | source_class={hit.source_class} | rank={hit.rank_score:.2f}"
            for hit in hits
        )
        result = await sdk.Runner.run(agent, input=f"Decide whether to scrape these exploratory hits:\n{payload}")
        decisions = {item.url: item for item in result.final_output.decisions}
        for hit in hits:
            decision = decisions.get(hit.url)
            if decision is None:
                hit.scrape_decision = "skip"
                hit.scrape_reason = "triage agent returned no decision"
                continue
            hit.scrape_decision = decision.decision
            hit.scrape_reason = decision.reason.strip() or "triage decision"

    def _triage_with_heuristics(self, city_target: CityTarget, hits: list[SearchHit]) -> None:
        for hit in hits:
            lowered = f"{hit.title} {hit.snippet} {hit.url}".casefold()
            domain = normalize_domain(hit.url)
            has_funding = any(keyword in lowered for keyword in config.FUNDING_HINTS)
            has_project_signal = any(keyword in lowered for keyword in PROJECT_KEYWORDS) or hit.url.lower().endswith(".pdf")
            official_like = (
                any(marker in domain for marker in config.OFFICIAL_DOMAIN_MARKERS)
                or any(alias.casefold().replace(" ", "") in domain.replace(".", "").replace("-", "") for alias in city_target.names)
            )

            if hit.source_class == "reject_external":
                hit.scrape_decision = "skip"
                hit.scrape_reason = "low-trust exploratory domain"
            elif official_like and (has_funding or has_project_signal):
                hit.scrape_decision = "scrape"
                hit.scrape_reason = "official-looking exploratory hit with project signal"
            elif has_funding and has_project_signal:
                hit.scrape_decision = "scrape"
                hit.scrape_reason = "strong funding and project signal"
            else:
                hit.scrape_decision = "skip"
                hit.scrape_reason = "weak exploratory signal"
