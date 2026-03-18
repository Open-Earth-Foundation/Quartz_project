from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .types import CityRunReport, CityRunSummary, VerifiedProject


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(a=left.casefold(), b=right.casefold()).ratio()


@dataclass
class MergeOutcome:
    registry_records: list[VerifiedProject]
    report: CityRunReport


class MergeAgent:
    def merge_city(
        self,
        existing_records: list[VerifiedProject],
        fresh_records: list[VerifiedProject],
        report: CityRunReport,
        *,
        refresh_existing: bool,
    ) -> MergeOutcome:
        fresh_records = self._dedupe_fresh_records(fresh_records)
        existing_by_key = {record.project_key: record for record in existing_records}
        matched_existing: set[str] = set()
        final_records: list[VerifiedProject] = []
        summary = CityRunSummary(rejected=len(report.rejected_candidates))

        for fresh in fresh_records:
            matched = existing_by_key.get(fresh.project_key)
            if matched is None:
                matched = next(
                    (
                        record
                        for record in existing_records
                        if _similarity(record.project_title, fresh.project_title) >= 0.88
                    ),
                    None,
                )
            if matched is None:
                summary.new += 1
                final_records.append(fresh)
                continue

            matched_existing.add(matched.project_key)
            merged = self._merge_record(matched, fresh)
            if merged.model_dump() == matched.model_dump():
                summary.unchanged += 1
            else:
                summary.updated += 1
            final_records.append(merged)

        for existing in existing_records:
            if existing.project_key in matched_existing:
                continue
            if refresh_existing:
                summary.removed_inactive += 1
            else:
                final_records.append(existing)

        report.accepted_projects = final_records
        report.summary = summary
        return MergeOutcome(registry_records=final_records, report=report)

    def _dedupe_fresh_records(self, fresh_records: list[VerifiedProject]) -> list[VerifiedProject]:
        deduped: list[VerifiedProject] = []
        for fresh in fresh_records:
            match_index = next(
                (
                    index
                    for index, existing in enumerate(deduped)
                    if existing.project_key == fresh.project_key
                    or _similarity(existing.project_title, fresh.project_title) >= 0.88
                ),
                None,
            )
            if match_index is None:
                deduped.append(fresh)
            else:
                deduped[match_index] = self._merge_record(deduped[match_index], fresh)
        return deduped

    @staticmethod
    def _merge_record(existing: VerifiedProject, fresh: VerifiedProject) -> VerifiedProject:
        data = existing.model_dump()
        fresh_data = fresh.model_dump()
        for field in ("summary", "status", "funding_source", "funding_programme", "currency", "funding_evidence", "status_evidence", "last_official_update", "last_verified_at"):
            if fresh_data.get(field):
                data[field] = fresh_data[field]
        if fresh_data.get("funding_amount") is not None:
            data["funding_amount"] = fresh_data["funding_amount"]
        data["is_active"] = fresh_data["is_active"]
        ranking = {
            "reject_external": 0,
            "supporting_external": 1,
            "municipal_entity": 2,
            "city_subdomain": 3,
            "city_root": 4,
        }
        data["source_class"] = (
            existing.source_class
            if ranking[existing.source_class] >= ranking[fresh.source_class]
            else fresh.source_class
        )
        data["climate_tags"] = sorted(set(existing.climate_tags) | set(fresh.climate_tags))
        data["source_urls"] = sorted(set(existing.source_urls) | set(fresh.source_urls))
        data["supporting_pdf_urls"] = sorted(set(existing.supporting_pdf_urls) | set(fresh.supporting_pdf_urls))
        return VerifiedProject(**data)
