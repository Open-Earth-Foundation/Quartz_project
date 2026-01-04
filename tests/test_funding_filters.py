import datetime

from agents.funding_classifier import (
    classify_funding_status,
    classify_implementation_status,
    dedupe_project_key,
)
from agents.funding_filter import filter_projects_by_scope


def test_classifiers_detect_status():
    assert classify_funding_status("Project was funded by a grant") == "funded"
    assert classify_funding_status("Construction completed") in {"completed", "in_implementation"}
    assert classify_implementation_status("Project is underway") in {"in_progress"}
    assert classify_implementation_status(None) is None


def test_filter_projects_by_scope_keeps_recent_funded():
    today = datetime.date.today()
    recent = today.replace(year=today.year - 1).isoformat()
    old = today.replace(year=today.year - 30).isoformat()
    projects = [
        {"ProjectTitle": "Keep", "ProjectStatus": "funded", "StartDate": recent},
        {"ProjectTitle": "Drop", "ProjectStatus": "funded", "StartDate": old},
    ]
    kept, dropped = filter_projects_by_scope(projects, years=20, accepted_statuses=["funded", "completed"])
    assert len(kept) == 1
    assert kept[0]["ProjectTitle"] == "Keep"
    assert len(dropped) == 1


def test_dedupe_key_is_deterministic():
    key1 = dedupe_project_key("Solar Roofs", "Paris", "2022")
    key2 = dedupe_project_key(" solar roofs ", "PARIS", "2022")
    assert key1 == key2
