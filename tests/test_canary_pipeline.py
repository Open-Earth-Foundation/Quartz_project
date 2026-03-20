from __future__ import annotations

import json
from pathlib import Path

import pytest

from quartz_agents.pipeline import CityProjectPipeline
from quartz_agents.types import CityTarget, DiscoveryQuery, ScrapedSource, SearchHit, VerificationResult, VerifiedProject


class StubSearchClient:
    def search(self, query: str, city_target: CityTarget) -> list[SearchHit]:
        slug = city_target.city.casefold()
        hits = {
            "krakow": [
                SearchHit(query=query, url="https://kegw.krakow.pl/life-pact", title="LIFE PACT Krakow", snippet="co-financed adaptation project ongoing"),
                SearchHit(query=query, url="https://news.example.com/krakow-life-pact", title="Life Pact news", snippet="coverage"),
            ],
            "warsaw": [
                SearchHit(query=query, url="https://um.warszawa.pl/green-tram", title="Green Tram Line", snippet="municipal investment funded and ongoing"),
                SearchHit(query=query, url="https://transport.warszawa.pl/green-tram", title="Green Tram Line extension", snippet="city transport investment ongoing"),
            ],
            "gdansk": [
                SearchHit(query=query, url="https://gdansk.pl/retention-park", title="Retention Park", snippet="climate adaptation project with funding ongoing"),
                SearchHit(query=query, url="https://reddit.com/r/gdansk/retention", title="reddit thread", snippet="discussion"),
            ],
        }
        return hits[slug]


class StubScraper:
    def collect_sources(self, city_target: CityTarget, hits: list[SearchHit]) -> list[ScrapedSource]:
        fixtures = {
            "Krakow": [
                ScrapedSource(
                    url="https://kegw.krakow.pl/life-pact",
                    title="LIFE PACT Krakow",
                    content=(
                        "LIFE PACT Krakow is an ongoing adaptation project. "
                        "The project is co-financed by the European Union and the City of Krakow. "
                        "Realizacja trwa in 2026."
                    ),
                    source_kind="html",
                    internal_links=[],
                    supporting_pdf_urls=["https://kegw.krakow.pl/life-pact-brochure.pdf"],
                ),
                ScrapedSource(
                    url="https://news.example.com/krakow-life-pact",
                    title="Life Pact news",
                    content="External coverage of the same funded climate project.",
                    source_kind="html",
                ),
            ],
            "Warsaw": [
                ScrapedSource(
                    url="https://um.warszawa.pl/green-tram",
                    title="Green Tram Line",
                    content=(
                        "Green Tram Line is a municipal mobility project in implementation. "
                        "Funded by the city budget and EU support. Ongoing works continue in 2026."
                    ),
                    source_kind="html",
                ),
                ScrapedSource(
                    url="https://transport.warszawa.pl/green-tram",
                    title="Green Tram Line",
                    content=(
                        "Municipal transport authority page. The Green Tram Line investment is funded and ongoing."
                    ),
                    source_kind="html",
                ),
            ],
            "Gdansk": [
                ScrapedSource(
                    url="https://gdansk.pl/retention-park",
                    title="Retention Park",
                    content=(
                        "Retention Park is an ongoing climate adaptation and stormwater retention investment. "
                        "The project received funding from the city budget and EU programme."
                    ),
                    source_kind="html",
                ),
                ScrapedSource(
                    url="https://reddit.com/r/gdansk/retention",
                    title="reddit thread",
                    content="People discussing a park.",
                    source_kind="html",
                ),
            ],
        }
        return fixtures[city_target.city]


class StubDiscoveryAgent:
    async def generate_queries(self, city_target: CityTarget) -> list[DiscoveryQuery]:
        return [
            DiscoveryQuery(query=f"{city_target.city} official climate projects", scope="bounded"),
            DiscoveryQuery(query=f"{city_target.city} funded municipal projects", scope="exploratory"),
        ]


class PassThroughTriageAgent:
    async def triage_hits(self, city_target: CityTarget, hits: list[SearchHit]) -> list[SearchHit]:
        for hit in hits:
            hit.scrape_decision = "scrape"
            hit.scrape_reason = "test pass-through"
        return hits


class StubVerificationAgent:
    async def verify_source(self, city_target: CityTarget, source: ScrapedSource) -> VerificationResult:
        return VerificationResult(
            source_class="city_root",
            accepted_projects=[
                VerifiedProject(
                    project_key=f"{city_target.city.casefold()}::checkpoint-project",
                    city=city_target.city,
                    country=city_target.country,
                    project_title=f"{city_target.city} Checkpoint Project",
                    summary="Checkpoint test project.",
                    status="active",
                    is_active=True,
                    climate_tags=["climate"],
                    source_urls=[source.url],
                    source_class="city_root",
                    last_verified_at="2026-03-20T00:00:00+00:00",
                )
            ],
            rejected_candidates=[],
        )


async def test_canary_pipeline_runs_end_to_end(tmp_path):
    registry_path = tmp_path / "registry.json"
    run_report_path = tmp_path / "report.json"
    cities_file = tmp_path / "cities.json"
    cities_file.write_text(
        json.dumps(
            {
                "cities": [
                    {"city": "Krakow", "country": "Poland", "aliases": ["Kraków"], "seed_domains": ["krakow.pl", "kegw.krakow.pl"]},
                    {"city": "Warsaw", "country": "Poland", "aliases": ["Warszawa"], "seed_domains": ["um.warszawa.pl", "eko.um.warszawa.pl"]},
                    {"city": "Gdansk", "country": "Poland", "aliases": ["Gdańsk"], "seed_domains": ["gdansk.pl"]},
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    pipeline = CityProjectPipeline(
        search_client=StubSearchClient(),
        scraper=StubScraper(),
        discovery_agent=StubDiscoveryAgent(),
    )
    report = await pipeline.run_batch(
        cities_file=cities_file,
        registry_file=registry_path,
        run_report_file=run_report_path,
        refresh_existing=True,
    )

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    records = registry["records"]
    titles = {record["project_title"] for record in records}
    assert titles == {"LIFE PACT Krakow", "Green Tram Line", "Retention Park"}
    assert report.summary.new == 3
    assert report.summary.rejected >= 2
    warsaw = next(item for item in records if item["city"] == "Warsaw")
    assert len(warsaw["source_urls"]) == 2
    warsaw_report = next(item for item in report.city_reports if item.city == "Warsaw")
    assert all(hit.scrape_decision == "scrape" for hit in warsaw_report.search_hits)
    assert {hit.query_scope for hit in warsaw_report.search_hits} == {"bounded"}
    review_log = Path(report.review_log_path).read_text(encoding="utf-8")
    assert "Borderline Rejections" in review_log
    hints_log = Path(report.hints_log_path).read_text(encoding="utf-8")
    assert "# Hint Suggestions" in hints_log
    assert "Likely Omitted Official/Municipal Projects" in hints_log


class CrashOnSecondCityScraper:
    def collect_sources(self, city_target: CityTarget, hits: list[SearchHit]) -> list[ScrapedSource]:
        if city_target.city == "Warsaw":
            raise RuntimeError("forced scraper failure")
        return [
            ScrapedSource(
                url=f"https://{city_target.city.casefold()}.example.com/project",
                title=f"{city_target.city} project",
                content="Ongoing funded climate project.",
                source_kind="html",
            )
        ]


class SimpleSearchClient:
    def search(self, query: str, city_target: CityTarget) -> list[SearchHit]:
        return [
            SearchHit(
                query=query,
                url=f"https://{city_target.city.casefold()}.example.com/project",
                title=f"{city_target.city} project",
                snippet="funded ongoing municipal climate project",
            )
        ]


async def test_canary_pipeline_checkpoints_after_each_city(tmp_path):
    registry_path = tmp_path / "registry.json"
    run_report_path = tmp_path / "report.json"
    cities_file = tmp_path / "cities.json"
    cities_file.write_text(
        json.dumps(
            {
                "cities": [
                    {"city": "Krakow", "country": "Poland", "aliases": ["Kraków"], "seed_domains": ["krakow.pl"]},
                    {"city": "Warsaw", "country": "Poland", "aliases": ["Warszawa"], "seed_domains": ["um.warszawa.pl"]},
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    pipeline = CityProjectPipeline(
        search_client=SimpleSearchClient(),
        scraper=CrashOnSecondCityScraper(),
        discovery_agent=StubDiscoveryAgent(),
        search_triage_agent=PassThroughTriageAgent(),
        verification_agent=StubVerificationAgent(),
    )

    with pytest.raises(RuntimeError, match="forced scraper failure"):
        await pipeline.run_batch(
            cities_file=cities_file,
            registry_file=registry_path,
            run_report_file=run_report_path,
            refresh_existing=True,
        )

    assert registry_path.exists()
    assert run_report_path.exists()

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["record_count"] == 1
    assert registry["records"][0]["city"] == "Krakow"
    assert registry["records"][0]["project_title"] == "Krakow Checkpoint Project"

    report = json.loads(run_report_path.read_text(encoding="utf-8"))
    assert len(report["city_reports"]) == 1
    assert report["city_reports"][0]["city"] == "Krakow"

    review_log_path = run_report_path.with_name(f"{run_report_path.stem}_review.md")
    hints_log_path = run_report_path.with_name(f"{run_report_path.stem}_hints.md")
    assert review_log_path.exists()
    assert hints_log_path.exists()
