from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import config
from bootstrap_local_agents import load_local_agents_package

load_local_agents_package()

from quartz_agents.pipeline import CityProjectPipeline  # type: ignore  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Quartz city climate project registry")
    parser.add_argument(
        "--cities-file",
        type=Path,
        default=config.DEFAULT_CITIES_FILE,
        help="Rich input JSON containing the target cities.",
    )
    parser.add_argument(
        "--registry-file",
        type=Path,
        default=config.DEFAULT_REGISTRY_FILE,
        help="Canonical JSON registry to rewrite in place.",
    )
    parser.add_argument(
        "--run-report-file",
        type=Path,
        default=config.DEFAULT_RUN_REPORT_FILE,
        help="Batch run report JSON path.",
    )
    parser.add_argument(
        "--max-cities",
        type=int,
        default=None,
        help="Limit the number of cities processed from the input file.",
    )
    parser.add_argument(
        "--refresh-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Re-verify existing records for processed cities and remove inactive ones.",
    )
    return parser


async def main_async() -> None:
    args = build_parser().parse_args()
    pipeline = CityProjectPipeline()
    result = await pipeline.run_batch(
        cities_file=args.cities_file,
        registry_file=args.registry_file,
        run_report_file=args.run_report_file,
        max_cities=args.max_cities,
        refresh_existing=args.refresh_existing,
    )
    print(f"Processed {len(result.city_reports)} city targets")
    print(f"Registry: {args.registry_file}")
    print(f"Run report: {args.run_report_file}")
    print(f"Review log: {result.review_log_path}")
    if result.hints_log_path:
        print(f"Hints log: {result.hints_log_path}")
    print(
        "Summary:"
        f" new={result.summary.new}"
        f" updated={result.summary.updated}"
        f" unchanged={result.summary.unchanged}"
        f" removed_inactive={result.summary.removed_inactive}"
        f" rejected={result.summary.rejected}"
    )


if __name__ == "__main__":
    asyncio.run(main_async())
