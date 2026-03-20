from __future__ import annotations

from quartz_agents.discovery_agent import DiscoveryAgent
from quartz_agents.types import CityTarget


async def test_discovery_fallback_queries_include_two_exploratory_and_six_bounded(monkeypatch):
    monkeypatch.setattr("quartz_agents.discovery_agent.sdk_available", lambda: False)

    agent = DiscoveryAgent()
    city = CityTarget(
        city="Warsaw",
        country="Poland",
        aliases=["Warszawa"],
        seed_domains=["um.warszawa.pl", "eko.um.warszawa.pl", "transport.warszawa.pl"],
    )

    queries = await agent.generate_queries(city)

    assert len(queries) == 8
    assert [item.scope for item in queries[:2]] == ["exploratory", "exploratory"]
    assert all("site:" not in item.query for item in queries[:2])
    assert sum(item.scope == "exploratory" for item in queries) == 2
    assert sum(item.scope == "bounded" for item in queries) == 6
    assert any(item.query.startswith("site:um.warszawa.pl ") for item in queries[2:])
    assert any("umowa o dofinansowanie" in item.query for item in queries[2:])


async def test_discovery_fallback_queries_fill_budget_for_root_only_city(monkeypatch):
    monkeypatch.setattr("quartz_agents.discovery_agent.sdk_available", lambda: False)

    agent = DiscoveryAgent()
    city = CityTarget(city="Aachen", country="Germany", aliases=[], seed_domains=["aachen.de"])

    queries = await agent.generate_queries(city)

    assert len(queries) == 8
    assert [item.scope for item in queries[:2]] == ["exploratory", "exploratory"]
    assert all("site:" not in item.query for item in queries[:2])
    assert any(item.query.startswith("site:aachen.de ") for item in queries[2:])
