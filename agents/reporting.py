"""Reporting helpers for funded project outputs."""
from __future__ import annotations

import csv
import json
import os
from typing import List, Dict, Any

import config


def export_funded_projects(
    projects: List[Dict[str, Any]],
    output_dir: str | None = None,
    filename_prefix: str | None = None,
) -> Dict[str, str]:
    """Write funded projects to CSV and JSON for downstream analysis."""
    output_dir = output_dir or config.FUNDED_REPORT_DIR
    os.makedirs(output_dir, exist_ok=True)

    prefix = filename_prefix or "funded_projects"
    json_path = os.path.join(output_dir, f"{prefix}.json")
    csv_path = os.path.join(output_dir, f"{prefix}.csv")

    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(projects, f_json, indent=2, ensure_ascii=False)

    fieldnames = sorted({k for p in projects for k in p.keys()})
    with open(csv_path, "w", encoding="utf-8", newline="") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
        writer.writeheader()
        for project in projects:
            writer.writerow({k: project.get(k, "") for k in fieldnames})

    return {"json": json_path, "csv": csv_path}
