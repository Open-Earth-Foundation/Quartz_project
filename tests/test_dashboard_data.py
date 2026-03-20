from __future__ import annotations

import json
from pathlib import Path

from dashboard_data import _resolve_optional_path, collect_dashboard, parse_hint_markdown


def test_parse_hint_markdown_extracts_city_sections():
    parsed = parse_hint_markdown(
        """# Hint Suggestions

Generated at: 2026-03-18T21:52:10.507499+00:00

## Summary
- accepted=20, rejected=38

## Krakow, Poland

### Candidate Hint Additions
- path_prefix: /aktualnosci
- query_fragment: tram

### Candidate Demotions
- None

### Likely Omitted Official/Municipal Projects
- Official project | https://example.com/project | strong funding signal

### Suspicious Accepted Records
- None
"""
    )

    assert parsed["summary_counts"] == {"accepted": 20, "rejected": 38}
    assert parsed["cities"][0]["city"] == "Krakow"
    assert parsed["cities"][0]["candidate_additions"][0] == {
        "kind": "path_prefix",
        "value": "/aktualnosci",
    }
    assert parsed["cities"][0]["omitted_projects"][0]["url"] == "https://example.com/project"


def test_parse_hint_markdown_sanitizes_pdf_blob_titles():
    parsed = parse_hint_markdown(
        """# Hint Suggestions

Generated at: 2026-03-18T21:52:10.507499+00:00

## Summary
- accepted=20, rejected=38

## Bologna, Italy

### Candidate Hint Additions
- path_prefix: /downloadalfresco/documentale

### Candidate Demotions
- None

### Likely Omitted Official/Municipal Projects
- %PDF-1.7 endobj endstream startxref %%EOF | https://wssol.comune.bologna.it/downloadalfresco/documentale/download?id=abc | borderline rejection: missing funding signal

### Suspicious Accepted Records
- None
"""
    )

    assert parsed["cities"][0]["omitted_projects"][0]["title"] == "PDF document from wssol.comune.bologna.it"


def test_collect_dashboard_aggregates_latest_runs(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    (runs_dir / "sample_registry.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-18T09:00:00+00:00",
                "record_count": 1,
                "records": [
                    {
                        "city": "Krakow",
                        "country": "Poland",
                        "project_title": "Sample project",
                        "is_active": True,
                        "last_verified_at": "2026-03-18T09:05:00+00:00",
                        "source_urls": ["https://example.com/project"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    (runs_dir / "sample_report.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-18T10:00:00+00:00",
                "registry_path": "runs/sample_registry.json",
                "review_log_path": "runs/sample_report_review.md",
                "city_reports": [
                    {
                        "city": "Krakow",
                        "country": "Poland",
                        "accepted_projects": [
                            {
                                "city": "Krakow",
                                "project_title": "Sample project",
                                "status": "active",
                                "source_urls": ["https://example.com/project"],
                            }
                        ],
                        "rejected_candidates": [{}, {}],
                    }
                ],
                "summary": {"new": 1, "updated": 0, "unchanged": 0, "rejected": 2},
            }
        ),
        encoding="utf-8",
    )

    (runs_dir / "sample_report_review.md").write_text("# Review\n", encoding="utf-8")
    (runs_dir / "sample_report_hints.md").write_text(
        """# Hint Suggestions

Generated at: 2026-03-18T10:05:00+00:00

## Summary
- accepted=1, rejected=2

## Krakow, Poland

### Candidate Hint Additions
- query_fragment: tram

### Candidate Demotions
- None

### Likely Omitted Official/Municipal Projects
- Missed project | https://example.com/missed | strong funding signal

### Suspicious Accepted Records
- None
""",
        encoding="utf-8",
    )

    (runs_dir / "sample_summary.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-18T10:10:00+00:00",
                "summary": {"new": 1, "updated": 0, "unchanged": 0, "rejected": 2},
                "cities": [{"city": "Krakow", "country": "Poland", "accepted": 1, "rejected": 2}],
                "artifacts": {"head_report": "runs/sample_report.json"},
            }
        ),
        encoding="utf-8",
    )

    dashboard = collect_dashboard(runs_dir)

    assert dashboard["artifact_counts"] == {
        "reports": 1,
        "summaries": 1,
        "registries": 1,
        "hints": 1,
    }
    assert dashboard["latest_report"]["name"] == "sample_report.json"
    assert dashboard["latest_report"]["hints"]["path"] == "runs/sample_report_hints.md"
    assert dashboard["latest_summary"]["cities"][0]["city"] == "Krakow"
    assert dashboard["latest_registry"]["active_count"] == 1
    assert dashboard["latest_hints"][0]["cities"][0]["candidate_additions"][0]["value"] == "tram"


def test_collect_dashboard_builds_funding_views(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    (runs_dir / "sample_registry.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-18T09:00:00+00:00",
                "record_count": 2,
                "records": [
                    {
                        "city": "Amsterdam",
                        "country": "Netherlands",
                        "project_title": "Programme Openbare ruimte, Water, Groen en Vervoer",
                        "summary": "The city budget allocates major funding to public space, water, green space, and transport upgrades.",
                        "funding_amount": 1266.8,
                        "currency": "EUR million",
                        "funding_source": "Gemeente Amsterdam",
                        "funding_programme": "Begroting 2024",
                        "climate_tags": ["mobility", "water", "greenspace"],
                        "is_active": True,
                        "last_verified_at": "2026-03-18T09:05:00+00:00",
                        "source_urls": ["https://example.com/amsterdam"],
                    },
                    {
                        "city": "Krakow",
                        "country": "Poland",
                        "project_title": "Rozwój inteligentnych systemów transportowych",
                        "summary": "Investment in intelligent transport systems to improve urban mobility and access across the city.",
                        "funding_amount": 46209240.17,
                        "currency": "PLN",
                        "funding_source": "Miasto Kraków",
                        "funding_programme": "ITS Kraków",
                        "climate_tags": ["mobility"],
                        "is_active": True,
                        "last_verified_at": "2026-03-18T09:10:00+00:00",
                        "source_urls": ["https://example.com/krakow"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    (runs_dir / "sample_report.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-18T10:00:00+00:00",
                "registry_path": "runs/sample_registry.json",
                "review_log_path": "runs/sample_report_review.md",
                "city_reports": [
                    {
                        "city": "Amsterdam",
                        "country": "Netherlands",
                        "accepted_projects": [
                            {
                                "city": "Amsterdam",
                                "country": "Netherlands",
                                "project_title": "Programme Openbare ruimte, Water, Groen en Vervoer",
                                "summary": "The city budget allocates major funding to public space, water, green space, and transport upgrades.",
                                "funding_amount": 1266.8,
                                "currency": "EUR million",
                                "funding_source": "Gemeente Amsterdam",
                                "funding_programme": "Begroting 2024",
                                "climate_tags": ["mobility", "water", "greenspace"],
                                "status": "active",
                                "source_urls": ["https://example.com/amsterdam"],
                            }
                        ],
                        "rejected_candidates": [],
                    }
                ],
                "summary": {"new": 1, "updated": 0, "unchanged": 0, "rejected": 0},
            }
        ),
        encoding="utf-8",
    )

    (runs_dir / "sample_report_review.md").write_text("# Review\n", encoding="utf-8")

    dashboard = collect_dashboard(runs_dir)

    registry = dashboard["latest_registry"]
    assert registry["funded_project_count"] == 2
    assert registry["cities_with_funding_count"] == 2
    assert registry["top_funded_projects"][0]["city"] == "Amsterdam"
    assert registry["top_funded_projects"][0]["funding_display"] == "EUR 1,266.8 million"
    assert registry["top_funded_projects"][0]["funding_display_short"] == "EUR 1.3B"
    assert "public space, water, green space, and transport upgrades." in registry["top_funded_projects"][0]["what_city_is_buying"]
    assert registry["city_spend_focus"][0]["headline_project"] == "Programme Openbare ruimte, Water, Groen en Vervoer"

    report = dashboard["latest_reports"][0]
    assert report["project_spotlight"][0]["funding_display"] == "EUR 1,266.8 million"
    assert report["project_spotlight"][0]["funding_source"] == "Gemeente Amsterdam"


def test_collect_dashboard_uses_latest_report_as_summary_fallback(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    (runs_dir / "sample_registry.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-18T09:00:00+00:00",
                "record_count": 1,
                "records": [
                    {
                        "city": "Krakow",
                        "country": "Poland",
                        "project_title": "Sample project",
                        "is_active": True,
                        "last_verified_at": "2026-03-18T09:05:00+00:00",
                        "source_urls": ["https://example.com/project"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    (runs_dir / "sample_report.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-18T10:00:00+00:00",
                "registry_path": "runs/sample_registry.json",
                "review_log_path": "runs/sample_report_review.md",
                "city_reports": [
                    {
                        "city": "Krakow",
                        "country": "Poland",
                        "accepted_projects": [
                            {
                                "city": "Krakow",
                                "project_title": "Sample project",
                                "status": "active",
                                "source_urls": ["https://example.com/project"],
                            }
                        ],
                        "rejected_candidates": [{}, {}],
                    }
                ],
                "summary": {"new": 1, "updated": 0, "unchanged": 0, "rejected": 2},
            }
        ),
        encoding="utf-8",
    )

    (runs_dir / "sample_report_review.md").write_text("# Review\n", encoding="utf-8")

    dashboard = collect_dashboard(runs_dir)

    assert dashboard["latest_summary"]["name"] == "sample_report.json"
    assert dashboard["latest_summary"]["summary"]["new"] == 1
    assert dashboard["latest_summary"]["artifacts"]["report"]["path"] == "runs/sample_report.json"


def test_resolve_optional_path_maps_windows_paths_in_wsl(monkeypatch):
    target = r"C:\Users\piotr\Documents\GitHub\Quartz_project\runs\sample_report_review.md"
    expected = Path("/mnt/c/Users/piotr/Documents/GitHub/Quartz_project/runs/sample_report_review.md")

    monkeypatch.setattr(Path, "is_absolute", lambda self: False)
    monkeypatch.setattr(Path, "exists", lambda self: self == expected)
    monkeypatch.setattr(Path, "resolve", lambda self: self)

    resolved = _resolve_optional_path(target, Path("/repo"))

    assert resolved == expected
