from __future__ import annotations

import json
import logging
from pathlib import Path

import config
from .discovery_agent import DiscoveryAgent
from .merge_agent import MergeAgent
from .registry import aggregate_summary, load_registry, save_hints_log, save_registry, save_run_report, write_review_log
from .review_agent import ReviewAgent
from .runtime import now_utc_iso
from .scrape import FirecrawlScraper
from .search import GoogleSearchClient, dedupe_and_rank_hits
from .search_triage_agent import SearchTriageAgent
from .types import BatchRunReport, CityBatchInput, CityRunReport, CityRunSummary, CityTarget, VerifiedProject, normalize_city_key
from .verification_agent import VerificationAgent

logger = logging.getLogger(__name__)


class CityProjectPipeline:
    def __init__(
        self,
        *,
        search_client: GoogleSearchClient | None = None,
        scraper: FirecrawlScraper | None = None,
        discovery_agent: DiscoveryAgent | None = None,
        search_triage_agent: SearchTriageAgent | None = None,
        verification_agent: VerificationAgent | None = None,
        merge_agent: MergeAgent | None = None,
        review_agent: ReviewAgent | None = None,
    ) -> None:
        self.search_client = search_client or GoogleSearchClient()
        self.scraper = scraper or FirecrawlScraper()
        self.discovery_agent = discovery_agent or DiscoveryAgent()
        self.search_triage_agent = search_triage_agent or SearchTriageAgent()
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
        logger.info(
            "Starting batch for %s cities from %s",
            len(city_targets),
            cities_file,
        )

        existing_registry = load_registry(registry_file)
        untouched_records: list[VerifiedProject] = []
        city_reports: list[CityRunReport] = []
        updated_registry: list[VerifiedProject] = []

        processed_city_keys = {normalize_city_key(target.city) for target in city_targets}
        for record in existing_registry:
            if normalize_city_key(record.city) not in processed_city_keys:
                untouched_records.append(record)

        review_log_path = run_report_file.with_name(f"{run_report_file.stem}_review.md")
        hints_log_path = run_report_file.with_name(f"{run_report_file.stem}_hints.md")

        batch_report: BatchRunReport | None = None

        for index, target in enumerate(city_targets, start=1):
            remaining = len(city_targets) - index
            logger.info(
                "[%s/%s] %s, %s | cities left: %s",
                index,
                len(city_targets),
                target.city,
                target.country,
                remaining,
            )
            query_plans = await self.discovery_agent.generate_queries(target)
            queries = [item.query for item in query_plans]
            logger.info("  queries: %s", len(query_plans))
            hits = []
            for item in query_plans[: config.MAX_DISCOVERY_QUERIES]:
                query_hits = self.search_client.search(item.query, target)
                for hit in query_hits:
                    hit.query_scope = item.scope
                hits.extend(query_hits)
            ranked_hits = dedupe_and_rank_hits(hits, target)
            logger.info("  ranked hits: %s", len(ranked_hits))
            triaged_hits = await self.search_triage_agent.triage_hits(target, ranked_hits)
            scrape_candidates = sum(1 for hit in triaged_hits if hit.scrape_decision != "skip")
            logger.info("  scrape candidates: %s", scrape_candidates)
            sources = self.scraper.collect_sources(target, triaged_hits)
            logger.info("  scraped sources: %s", len(sources))

            accepted: list[VerifiedProject] = []
            rejected = []
            for source in sources:
                result = await self.verification_agent.verify_source(target, source)
                accepted.extend(result.accepted_projects)
                rejected.extend(result.rejected_candidates)
            logger.info("  accepted: %s | rejected: %s", len(accepted), len(rejected))

            city_report = CityRunReport(
                city=target.city,
                country=target.country,
                queries=queries,
                search_hits=triaged_hits,
                rejected_candidates=rejected,
            )
            city_existing = [record for record in existing_registry if normalize_city_key(record.city) == normalize_city_key(target.city)]
            merge_outcome = self.merge_agent.merge_city(
                city_existing,
                accepted,
                city_report,
                refresh_existing=refresh_existing,
            )
            updated_registry.extend(merge_outcome.registry_records)
            city_reports.append(merge_outcome.report)
            logger.info(
                "  summary: new=%s updated=%s unchanged=%s removed_inactive=%s",
                merge_outcome.report.summary.new,
                merge_outcome.report.summary.updated,
                merge_outcome.report.summary.unchanged,
                merge_outcome.report.summary.removed_inactive,
            )
            batch_report = self._save_checkpoint(
                registry_file=registry_file,
                run_report_file=run_report_file,
                review_log_path=review_log_path,
                hints_log_path=hints_log_path,
                final_registry=untouched_records + updated_registry,
                city_reports=city_reports,
                city_targets=city_targets,
            )

        if batch_report is None:
            batch_report = self._save_checkpoint(
                registry_file=registry_file,
                run_report_file=run_report_file,
                review_log_path=review_log_path,
                hints_log_path=hints_log_path,
                final_registry=untouched_records + updated_registry,
                city_reports=city_reports,
                city_targets=city_targets,
            )
        logger.info("Batch complete. Registry: %s", registry_file)
        logger.info("Batch complete. Run report: %s", run_report_file)
        return batch_report

    def _build_batch_report(
        self,
        *,
        registry_file: Path,
        review_log_path: Path,
        hints_log_path: Path,
        city_reports: list[CityRunReport],
    ) -> BatchRunReport:
        return BatchRunReport(
            generated_at=now_utc_iso(),
            registry_path=str(registry_file),
            review_log_path=str(review_log_path),
            hints_log_path=str(hints_log_path),
            city_reports=list(city_reports),
            summary=aggregate_summary(city_reports),
        )

    def _save_checkpoint(
        self,
        *,
        registry_file: Path,
        run_report_file: Path,
        review_log_path: Path,
        hints_log_path: Path,
        final_registry: list[VerifiedProject],
        city_reports: list[CityRunReport],
        city_targets: list[CityTarget],
    ) -> BatchRunReport:
        batch_report = self._build_batch_report(
            registry_file=registry_file,
            review_log_path=review_log_path,
            hints_log_path=hints_log_path,
            city_reports=city_reports,
        )
        save_registry(registry_file, final_registry)
        save_run_report(run_report_file, batch_report)
        write_review_log(review_log_path, batch_report)
        hints_markdown = self.review_agent.build_hints_markdown(batch_report, city_targets)
        save_hints_log(hints_log_path, hints_markdown)
        logger.info("  checkpoint saved: %s cities persisted", len(city_reports))
        return batch_report
