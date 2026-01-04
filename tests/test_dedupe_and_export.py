import json
from pathlib import Path

from agents.funding_classifier import dedupe_project_key
from agents.reporting import export_funded_projects


def test_golden_projects_have_unique_dedupe_keys():
    golden_path = Path(__file__).parent / "data" / "golden_projects.json"
    data = json.loads(golden_path.read_text())
    keys = {dedupe_project_key(p["ProjectTitle"], p["CityName"], p["StartDate"][:4]) for p in data}
    assert len(keys) == len(data)


def test_export_creates_files(tmp_path):
    projects = [
        {"ProjectTitle": "Test", "CityName": "City", "StartDate": "2022-01-01", "ProjectStatus": "funded"},
    ]
    paths = export_funded_projects(projects, output_dir=str(tmp_path))
    assert Path(paths["json"]).exists()
    assert Path(paths["csv"]).exists()
