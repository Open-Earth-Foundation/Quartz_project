#!/usr/bin/env python3
"""Refresh vector-ready payloads including funding fields."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any

RUNS_DIR = Path("runs")
LOG_PATH = Path("logs/index_rebuild.json")


def collect_records() -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not RUNS_DIR.exists():
        return records
    for fpath in RUNS_DIR.glob("*.json"):
        try:
            payload = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in payload.get("structured_data", []):
            records.append(
                {
                    "ProjectTitle": item.get("ProjectTitle") or item.get("project_name"),
                    "City": (item.get("Location") or {}).get("CityName") if isinstance(item.get("Location"), dict) else item.get("city"),
                    "FundingAmount": (item.get("Financing") or {}).get("TotalProjectCost"),
                    "FundingSource": (item.get("Funders") or {}).get("PrimaryFunderName") if isinstance(item.get("Funders"), dict) else item.get("funding_source"),
                    "SourceUrl": (item.get("Traceability") or {}).get("SourceUrl") if isinstance(item.get("Traceability"), dict) else item.get("url"),
                }
            )
    return records


def main() -> None:
    os.makedirs(LOG_PATH.parent, exist_ok=True)
    records = collect_records()
    LOG_PATH.write_text(json.dumps({"records_indexed": len(records), "fields": ["ProjectTitle", "City", "FundingAmount", "FundingSource", "SourceUrl"]}, indent=2))
    print(f"Indexed {len(records)} records into {LOG_PATH}")


if __name__ == "__main__":
    main()
