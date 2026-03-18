from __future__ import annotations

from quartz_agents.merge_agent import MergeAgent
from quartz_agents.types import CityRunReport, SourceClass, VerifiedProject


def _project(title: str, source_class: SourceClass, url: str, *, amount: float | None = None) -> VerifiedProject:
    return VerifiedProject(
        project_key=f"warsaw::{title.lower().replace(' ', '-')}",
        city="Warsaw",
        country="Poland",
        project_title=title,
        summary="summary",
        status="in_implementation",
        is_active=True,
        climate_tags=["mobility"],
        source_urls=[url],
        source_class=source_class,
        supporting_pdf_urls=[],
        funding_source="City",
        funding_programme="EU",
        funding_amount=amount,
        currency="EUR",
        funding_evidence="funded",
        status_evidence="ongoing",
        last_official_update="2025-01-01",
        last_verified_at="2026-03-18T00:00:00+00:00",
    )


def test_merge_updates_and_preserves_highest_confidence():
    merger = MergeAgent()
    existing = [_project("Green Tram Line", "municipal_entity", "https://news.example.com/tram")]
    fresh = [_project("Green Tram Line", "city_root", "https://um.warszawa.pl/tram", amount=2000000)]
    report = CityRunReport(city="Warsaw", country="Poland")
    outcome = merger.merge_city(existing, fresh, report, refresh_existing=True)
    merged = outcome.registry_records[0]
    assert merged.source_class == "city_root"
    assert len(merged.source_urls) == 2
    assert merged.funding_amount == 2000000
    assert outcome.report.summary.updated == 1


def test_merge_removes_unmatched_existing_when_refreshing():
    merger = MergeAgent()
    existing = [_project("Old Project", "city_root", "https://um.warszawa.pl/old")]
    report = CityRunReport(city="Warsaw", country="Poland")
    outcome = merger.merge_city(existing, [], report, refresh_existing=True)
    assert outcome.registry_records == []
    assert outcome.report.summary.removed_inactive == 1
