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
