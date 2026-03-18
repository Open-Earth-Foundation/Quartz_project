from __future__ import annotations

import json
from pathlib import Path

import config
from .discovery_agent import DiscoveryAgent
from .merge_agent import MergeAgent
from .registry import aggregate_summary, load_registry, save_hints_log, save_registry, save_run_report, write_review_log
from .review_agent import ReviewAgent
from .runtime import now_utc_iso
from .scrape import FirecrawlScraper
from .search import GoogleSearchClient, dedupe_and_rank_hits
from .types import BatchRunReport, CityBatchInput, CityRunReport, CityRunSummary, VerifiedProject
from .verification_agent import VerificationAgent


class CityProjectPipeline:
    def __init__(
        self,
        *,
        search_client: GoogleSearchClient | None = None,
        scraper: FirecrawlScraper | None = None,
        discovery_agent: DiscoveryAgent | None = None,
        verification_agent: VerificationAgent | None = None,
        merge_agent: MergeAgent | None = None,
        review_agent: ReviewAgent | None = None,
    ) -> None:
        self.search_client = search_client or GoogleSearchClient()
        self.scraper = scraper or FirecrawlScraper()
        self.discovery_agent = discovery_agent or DiscoveryAgent()
        self.verification_agent = verification_agent or VerificationAgent()
        self.merge_agent = merge_agent or MergeAgent()
        self.review_agent = review_agent or ReviewAgent()

    async def run_batch(
        self,
        *,
        cities_file: Path,
        registry_file: Path,
        run_report_file: Path,
        max_cities: int | None = None,
        refresh_existing: bool = True,
    ) -> BatchRunReport:
        batch = CityBatchInput.model_validate(json.loads(cities_file.read_text(encoding="utf-8")))
        city_targets = batch.cities[:max_cities] if max_cities else batch.cities

        existing_registry = load_registry(registry_file)
        untouched_records: list[VerifiedProject] = []
        city_reports: list[CityRunReport] = []
        updated_registry: list[VerifiedProject] = []

        processed_city_keys = {target.city.casefold() for target in city_targets}
        for record in existing_registry:
            if record.city.casefold() not in processed_city_keys:
                untouched_records.append(record)

        for target in city_targets:
            queries = await self.discovery_agent.generate_queries(target)
            hits = []
            for query in queries[: config.MAX_DISCOVERY_QUERIES]:
                hits.extend(self.search_client.search(query, target))
            ranked_hits = dedupe_and_rank_hits(hits, target)
            sources = self.scraper.collect_sources(target, ranked_hits)

            accepted: list[VerifiedProject] = []
            rejected = []
            for source in sources:
                result = await self.verification_agent.verify_source(target, source)
                accepted.extend(result.accepted_projects)
                rejected.extend(result.rejected_candidates)

            city_report = CityRunReport(
                city=target.city,
                country=target.country,
                queries=queries,
                search_hits=ranked_hits,
                rejected_candidates=rejected,
            )
            city_existing = [record for record in existing_registry if record.city.casefold() == target.city.casefold()]
            merge_outcome = self.merge_agent.merge_city(
                city_existing,
                accepted,
                city_report,
                refresh_existing=refresh_existing,
            )
            updated_registry.extend(merge_outcome.registry_records)
            city_reports.append(merge_outcome.report)

        final_registry = untouched_records + updated_registry
        save_registry(registry_file, final_registry)

        review_log_path = run_report_file.with_name(f"{run_report_file.stem}_review.md")
        hints_log_path = run_report_file.with_name(f"{run_report_file.stem}_hints.md")
        batch_report = BatchRunReport(
            generated_at=now_utc_iso(),
            registry_path=str(registry_file),
            review_log_path=str(review_log_path),
            hints_log_path=str(hints_log_path),
            city_reports=city_reports,
            summary=aggregate_summary(city_reports),
        )
        save_run_report(run_report_file, batch_report)
        write_review_log(review_log_path, batch_report)
        hints_markdown = self.review_agent.build_hints_markdown(batch_report, city_targets)
        save_hints_log(hints_log_path, hints_markdown)
        return batch_report
