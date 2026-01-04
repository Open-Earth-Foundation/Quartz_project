import datetime

from agents.funding_scope import gate_project_scope, status_is_funded
from agents import extraction_flow


def test_gate_requires_funded_and_recent():
    today = datetime.date.today()
    recent = today.replace(year=today.year - 1).strftime("%Y-%m-%d")
    old = today.replace(year=today.year - 25).strftime("%Y-%m-%d")

    funded_recent = gate_project_scope("completed", recent, None)
    assert funded_recent["in_scope"] is True

    funded_old = gate_project_scope("completed", old, None)
    assert funded_old["in_scope"] is False

    not_funded_recent = gate_project_scope("planned", recent, None)
    assert not_funded_recent["in_scope"] is False


def test_merge_partial_preserves_prior_values():
    base = {"ProjectTitle": "Old", "Financing": {"CurrencyCode": "USD"}, "Funders": None}
    new = {"ProjectTitle": None, "Financing": {"TotalProjectCost": 1000000}, "Funders": {"PrimaryFunderName": "City"}}
    merged = extraction_flow.merge_partial(base, new)
    assert merged["ProjectTitle"] == "Old"  # unchanged
    assert merged["Financing"]["CurrencyCode"] == "USD"
    assert merged["Financing"]["TotalProjectCost"] == 1000000
    assert merged["Funders"]["PrimaryFunderName"] == "City"


def test_followup_detects_missing_final_fields():
    project = extraction_flow.init_partial_project()
    project["ProjectTitle"] = "Solar Roofs"
    project["Location"] = {"CityName": "Paris", "Country": "France"}
    missing = extraction_flow.collect_missing_fields(project, extraction_flow.CRITICAL_FINAL_FIELDS)
    assert "Funders" in missing
    assert extraction_flow.should_trigger_followup(project) is True
    follow = extraction_flow.build_followup_request(project)
    assert "needed_fields" in follow and "Funders" in follow["needed_fields"]
