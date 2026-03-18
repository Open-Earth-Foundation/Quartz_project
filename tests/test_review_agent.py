from __future__ import annotations

from quartz_agents.review_agent import ReviewAgent
from quartz_agents.types import (
    BatchRunReport,
    CityRunReport,
    CityRunSummary,
    CityTarget,
    RejectedCandidate,
    SearchHit,
    VerifiedProject,
)


def test_review_agent_generates_hint_additions_demotions_and_omissions():
    agent = ReviewAgent()
    city = CityTarget(city="Testopolis", country="Poland", aliases=[], seed_domains=["testopolis.pl"])
    accepted = [
        VerifiedProject(
            project_key="testopolis::strategy",
            city="Testopolis",
            country="Poland",
            project_title="City Development Strategy 2030",
            summary="summary",
            status="active",
            is_active=True,
            climate_tags=["adaptation"],
            source_urls=["https://testopolis.pl/strategy"],
            source_class="city_root",
            supporting_pdf_urls=[],
            funding_source="City budget",
            funding_programme=None,
            funding_amount=None,
            currency="PLN",
            funding_evidence="City budget funded the action.",
            status_evidence="ongoing",
            last_official_update="2026-01-01",
            last_verified_at="2026-03-18T00:00:00+00:00",
        )
    ]
    search_hits = [
        SearchHit(
            query="testopolis climate projects",
            url="https://climate.testopolis.pl/projects/feniks-green-tram",
            title="Municipal Green Tram project",
            snippet="Projekt dofinansowany z FEnIKS i realizowany przez miasto.",
            source_class="municipal_entity",
        ),
        SearchHit(
            query="testopolis climate projects",
            url="https://example-university.edu/scientific-projects/green-transition",
            title="University climate project",
            snippet="Research project about the climate transition.",
            source_class="supporting_external",
        ),
    ]
    rejected = [
        RejectedCandidate(
            url="https://climate.testopolis.pl/projects/feniks-green-tram",
            title="Municipal Green Tram project",
            source_class="municipal_entity",
            reason="missing active signal",
            borderline=True,
        )
    ]
    report = BatchRunReport(
        generated_at="2026-03-18T00:00:00+00:00",
        registry_path="runs/test_registry.json",
        review_log_path="runs/test_review.md",
        hints_log_path="runs/test_hints.md",
        city_reports=[
            CityRunReport(
                city="Testopolis",
                country="Poland",
                search_hits=search_hits,
                accepted_projects=accepted,
                rejected_candidates=rejected,
                summary=CityRunSummary(new=1, rejected=1),
            )
        ],
        summary=CityRunSummary(new=1, rejected=1),
    )

    markdown = agent.build_hints_markdown(report, [city])

    assert "domain: climate.testopolis.pl" in markdown
    assert "path_prefix: /projects/feniks-green-tram" in markdown
    assert "query_fragment: feniks" in markdown
    assert "domain: example-university.edu" in markdown
    assert "Municipal Green Tram project | https://climate.testopolis.pl/projects/feniks-green-tram" in markdown
    assert "City Development Strategy 2030 | https://testopolis.pl/strategy" in markdown


def test_review_agent_does_not_suggest_demoting_known_official_domains():
    agent = ReviewAgent()
    city = CityTarget(city="Warsaw", country="Poland", aliases=["Warszawa"], seed_domains=["um.warszawa.pl"])
    report = BatchRunReport(
        generated_at="2026-03-18T00:00:00+00:00",
        registry_path="runs/test_registry.json",
        review_log_path="runs/test_review.md",
        hints_log_path="runs/test_hints.md",
        city_reports=[
            CityRunReport(
                city="Warsaw",
                country="Poland",
                search_hits=[
                    SearchHit(
                        query="warsaw climate projects",
                        url="https://um.warszawa.pl/waw/europa/aktualnosci",
                        title="Aktualności - Europejska Warszawa",
                        snippet="Official city page",
                        source_class="city_root",
                    )
                ],
                rejected_candidates=[
                    RejectedCandidate(
                        url="https://um.warszawa.pl/waw/europa/aktualnosci",
                        title="Aktualności - Europejska Warszawa",
                        source_class="city_root",
                        reason="profile or category page rather than a funded project record",
                        borderline=True,
                    )
                ],
                summary=CityRunSummary(rejected=1),
            )
        ],
        summary=CityRunSummary(rejected=1),
    )

    markdown = agent.build_hints_markdown(report, [city])

    assert "domain: um.warszawa.pl" not in markdown
