from __future__ import annotations

from quartz_agents.search_triage_agent import SearchTriageAgent
from quartz_agents.types import CityTarget, SearchHit


async def test_search_triage_heuristics_gate_exploratory_hits(monkeypatch):
    monkeypatch.setattr("quartz_agents.search_triage_agent.sdk_available", lambda: False)
    monkeypatch.setattr("quartz_agents.search_triage_agent.config.MAX_EXPLORATORY_TRIAGE_HITS", 1)

    agent = SearchTriageAgent()
    city = CityTarget(city="Testopolis", country="Poland", aliases=[], seed_domains=["testopolis.pl"])
    hits = [
        SearchHit(
            query="testopolis official climate projects",
            query_scope="bounded",
            url="https://news.example.com/testopolis-grant",
            title="External coverage",
            snippet="Coverage of a municipal grant.",
            source_class="supporting_external",
        ),
        SearchHit(
            query="testopolis funded municipal projects",
            query_scope="exploratory",
            url="https://climate.testopolis.pl/projects/green-tram",
            title="Green Tram",
            snippet="Municipal funded mobility project.",
            source_class="municipal_entity",
        ),
        SearchHit(
            query="testopolis funded municipal projects",
            query_scope="exploratory",
            url="https://climate.testopolis.gov/project/award",
            title="Climate grant project",
            snippet="Official project page with grant funding.",
            source_class="supporting_external",
        ),
        SearchHit(
            query="testopolis funded municipal projects",
            query_scope="exploratory",
            url="https://reddit.com/r/testopolis/comments/green_tram",
            title="Reddit thread",
            snippet="People discussing the tram project.",
            source_class="reject_external",
        ),
    ]

    triaged = await agent.triage_hits(city, hits)

    assert triaged[0].scrape_decision == "scrape"
    assert triaged[0].scrape_reason == "bounded query"
    assert triaged[1].scrape_decision == "scrape"
    assert triaged[1].scrape_reason == "exploratory hit is already in city ecosystem"
    assert triaged[2].scrape_decision == "scrape"
    assert "official-looking exploratory hit" in triaged[2].scrape_reason
    assert triaged[3].scrape_decision == "skip"
    assert triaged[3].scrape_reason == "outside exploratory triage budget"
