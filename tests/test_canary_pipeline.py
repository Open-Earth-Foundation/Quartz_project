from __future__ import annotations

import json
from pathlib import Path

from quartz_agents.pipeline import CityProjectPipeline
from quartz_agents.types import CityTarget, ScrapedSource, SearchHit


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
    async def generate_queries(self, city_target: CityTarget) -> list[str]:
        return [f"{city_target.city} official climate projects", f"{city_target.city} funded municipal projects"]


async def test_canary_pipeline_runs_end_to_end(tmp_path):
    registry_path = tmp_path / "registry.json"
    run_report_path = tmp_path / "report.json"
    cities_file = tmp_path / "cities.json"
    cities_file.write_text(Path("NZC.json").read_text(encoding="utf-8"), encoding="utf-8")

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
    review_log = Path(report.review_log_path).read_text(encoding="utf-8")
    assert "Borderline Rejections" in review_log
    hints_log = Path(report.hints_log_path).read_text(encoding="utf-8")
    assert "# Hint Suggestions" in hints_log
    assert "Likely Omitted Official/Municipal Projects" in hints_log
