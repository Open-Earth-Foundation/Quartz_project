from __future__ import annotations

from pathlib import Path

from .runtime import dump_json, ensure_runs_dir, now_utc_iso
from .types import BatchRunReport, CityRunReport, CityRunSummary, VerifiedProject


def load_registry(path: Path) -> list[VerifiedProject]:
    if not path.exists():
        return []
    payload = path.read_text(encoding="utf-8").strip()
    if not payload:
        return []
    import json

    raw = json.loads(payload)
    if isinstance(raw, list):
        records = raw
    else:
        records = raw.get("records", [])
    return [VerifiedProject(**item) for item in records]


def save_registry(path: Path, records: list[VerifiedProject]) -> None:
    ensure_runs_dir()
    dump_json(
        path,
        {
            "generated_at": now_utc_iso(),
            "record_count": len(records),
            "records": [record.model_dump(mode="json") for record in records],
        },
    )


def save_run_report(path: Path, report: BatchRunReport) -> None:
    ensure_runs_dir()
    dump_json(path, report.model_dump(mode="json"))


def save_hints_log(path: Path, content: str) -> None:
    ensure_runs_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_review_log(path: Path, report: BatchRunReport) -> None:
    lines = ["# Canary Review Log", ""]
    lines.append(f"Generated at: {report.generated_at}")
    lines.append("")
    lines.append("## Summary")
    lines.append(
        f"- new={report.summary.new}, updated={report.summary.updated}, unchanged={report.summary.unchanged}, "
        f"removed_inactive={report.summary.removed_inactive}, rejected={report.summary.rejected}"
    )
    lines.append("")
    for city_report in report.city_reports:
        lines.append(f"## {city_report.city}, {city_report.country}")
        lines.append("")
        lines.append("### Accepted Projects")
        if city_report.accepted_projects:
            for project in city_report.accepted_projects:
                lines.append(
                    f"- {project.project_title} | status={project.status} | source_class={project.source_class} | source={project.source_urls[0]}"
                )
        else:
            lines.append("- None")
        lines.append("")
        lines.append("### Borderline Rejections")
        borderlines = [item for item in city_report.rejected_candidates if item.borderline]
        if borderlines:
            for item in borderlines:
                lines.append(f"- {item.title or item.url} | {item.reason}")
        else:
            lines.append("- None")
        lines.append("")
        lines.append("### Manual Notes")
        lines.append("- Review accepted titles, funding, and active status.")
        lines.append("- Review borderline rejections for missed flagship projects.")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def aggregate_summary(city_reports: list[CityRunReport]) -> CityRunSummary:
    summary = CityRunSummary()
    for report in city_reports:
        summary.new += report.summary.new
        summary.updated += report.summary.updated
        summary.unchanged += report.summary.unchanged
        summary.removed_inactive += report.summary.removed_inactive
        summary.rejected += report.summary.rejected
    return summary
