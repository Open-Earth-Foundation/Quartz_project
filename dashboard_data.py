from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PureWindowsPath
from typing import Any

from text_safety import sanitize_display_title

SUMMARY_COUNTS_PATTERN = re.compile(r"([a-z_]+)=(\d+)")
MILLION_UNIT_MARKERS = ("million", "mln", "m€", "mio.", "miljoner")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fallback_timestamp(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _run_relative_path(path: Path, runs_dir: Path) -> str:
    return f"runs/{path.relative_to(runs_dir).as_posix()}"


def _run_link(path: Path | None, runs_dir: Path) -> dict[str, str] | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        relative = _run_relative_path(path, runs_dir)
    except ValueError:
        return None
    return {"path": relative, "url": f"/{relative}"}


def _resolve_optional_path(target: str | None, project_root: Path) -> Path | None:
    if not target:
        return None

    candidate = Path(target)
    if not candidate.is_absolute():
        windows_candidate = PureWindowsPath(target)
        if windows_candidate.drive and windows_candidate.root:
            drive = windows_candidate.drive.rstrip(":").lower()
            mapped = Path("/mnt") / drive / Path(*windows_candidate.parts[1:])
            candidate = mapped
        else:
            candidate = project_root / candidate
    if not candidate.exists():
        return None
    return candidate.resolve()


def _artifact_timestamp(payload: dict[str, Any], path: Path) -> datetime:
    for field in ("generated_at", "last_verified_at", "created_at"):
        timestamp = _parse_datetime(payload.get(field))
        if timestamp is not None:
            return timestamp
    return _fallback_timestamp(path)


def _summarize_counts(bullets: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for bullet in bullets:
        for key, value in SUMMARY_COUNTS_PATTERN.findall(bullet):
            counts[key] = int(value)
    return counts


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_decimal(value: float) -> str:
    if value.is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _compact_number(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}".rstrip("0").rstrip(".") + "B"
    if absolute >= 1_000_000:
        return f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if absolute >= 1_000:
        return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return _format_decimal(value)


def _currency_code(currency: str | None) -> str:
    lowered = str(currency or "").casefold()
    if "eur" in lowered or "m€" in lowered:
        return "EUR"
    if "pln" in lowered or "zł" in lowered:
        return "PLN"
    if "kr" in lowered or "kronor" in lowered:
        return "KR"
    return (currency or "").strip() or "Amount"


def _is_million_unit(currency: str | None) -> bool:
    lowered = str(currency or "").casefold()
    return any(marker in lowered for marker in MILLION_UNIT_MARKERS)


def _normalized_funding_amount(amount: Any, currency: str | None) -> float | None:
    numeric = _coerce_float(amount)
    if numeric is None:
        return None
    if _is_million_unit(currency):
        return numeric * 1_000_000
    return numeric


def _format_funding_amount(amount: Any, currency: str | None, *, compact: bool = False) -> str | None:
    numeric = _coerce_float(amount)
    if numeric is None:
        return None

    if compact:
        base_value = _normalized_funding_amount(numeric, currency) or numeric
        return f"{_currency_code(currency)} {_compact_number(base_value)}"

    formatted_number = _format_decimal(numeric)
    raw_currency = (currency or "").strip()
    lowered = raw_currency.casefold()
    if raw_currency == "EUR":
        return f"EUR {formatted_number}"
    if lowered in {"eur million", "eur mln", "m€"}:
        return f"EUR {formatted_number} million"
    if raw_currency == "PLN":
        return f"PLN {formatted_number}"
    if raw_currency:
        return f"{formatted_number} {raw_currency}"
    return formatted_number


def _truncate_text(value: str | None, limit: int = 180) -> str:
    collapsed = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def _purchase_focus(summary: str, title: str) -> str:
    cleaned_summary = re.sub(r"\s+", " ", summary).strip()
    if not cleaned_summary:
        return title
    first_sentence = re.split(r"(?<=[.!?])\s+|;\s+", cleaned_summary, maxsplit=1)[0].strip()
    return _truncate_text(first_sentence or cleaned_summary, 170)


def _project_snapshot(record: dict[str, Any], *, default_city: str = "Unknown", default_country: str = "") -> dict[str, Any]:
    source_urls = record.get("source_urls") or []
    source_url = source_urls[0] if source_urls else None
    summary = str(record.get("summary") or "").strip()
    title = sanitize_display_title(record.get("project_title") or "Untitled project", source_url)
    funding_display = _format_funding_amount(record.get("funding_amount"), record.get("currency"))
    funding_display_short = _format_funding_amount(record.get("funding_amount"), record.get("currency"), compact=True)

    return {
        "city": record.get("city") or default_city,
        "country": record.get("country") or default_country,
        "title": title,
        "summary": _truncate_text(summary, 240),
        "what_city_is_buying": _purchase_focus(summary, title),
        "status": record.get("status"),
        "funding_amount": record.get("funding_amount"),
        "currency": record.get("currency"),
        "funding_display": funding_display,
        "funding_display_short": funding_display_short,
        "funding_source": record.get("funding_source"),
        "funding_programme": record.get("funding_programme"),
        "climate_tags": [str(tag) for tag in (record.get("climate_tags") or [])][:4],
        "source_url": source_url,
        "last_verified_at": record.get("last_verified_at"),
        "_funding_sort": _normalized_funding_amount(record.get("funding_amount"), record.get("currency")) or -1.0,
    }


def _strip_project_internal_fields(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in items:
        shallow_copy = dict(item)
        shallow_copy.pop("_funding_sort", None)
        cleaned.append(shallow_copy)
    return cleaned


def _parse_hint_candidate(item: str) -> dict[str, str]:
    kind, separator, value = item.partition(":")
    if separator:
        return {"kind": kind.strip(), "value": value.strip()}
    return {"kind": "note", "value": item.strip()}


def _parse_hint_reference(item: str) -> dict[str, str | None]:
    parts = [part.strip() for part in item.split(" | ")]
    if len(parts) >= 3 and parts[1].startswith(("http://", "https://")):
        return {
            "title": sanitize_display_title(parts[0], parts[1]),
            "url": parts[1],
            "notes": " | ".join(parts[2:]),
        }
    return {"title": sanitize_display_title(item.strip()), "url": None, "notes": None}


def parse_hint_markdown(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "generated_at": None,
        "summary_bullets": [],
        "summary_counts": {},
        "cities": [],
    }

    current_city: dict[str, Any] | None = None
    current_section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("Generated at:"):
            result["generated_at"] = line.partition(":")[2].strip()
            continue

        if line.startswith("## "):
            heading = line[3:].strip()
            current_section = None
            if heading == "Summary":
                current_city = None
                continue

            city, separator, country = heading.partition(",")
            current_city = {
                "city": city.strip(),
                "country": country.strip() if separator else "",
                "candidate_additions": [],
                "candidate_demotions": [],
                "omitted_projects": [],
                "suspicious_records": [],
            }
            result["cities"].append(current_city)
            continue

        if line.startswith("### "):
            current_section = line[4:].strip()
            continue

        if not line.startswith("- "):
            continue

        item = line[2:].strip()
        if current_city is None:
            result["summary_bullets"].append(item)
            continue

        if current_section == "Candidate Hint Additions":
            if item != "None":
                current_city["candidate_additions"].append(_parse_hint_candidate(item))
            continue

        if current_section == "Candidate Demotions":
            if item != "None":
                current_city["candidate_demotions"].append(item)
            continue

        if current_section == "Likely Omitted Official/Municipal Projects":
            if item != "None":
                current_city["omitted_projects"].append(_parse_hint_reference(item))
            continue

        if current_section == "Suspicious Accepted Records":
            if item != "None":
                current_city["suspicious_records"].append(_parse_hint_reference(item))

    result["summary_counts"] = _summarize_counts(result["summary_bullets"])
    return result


def _build_hint_card(path: Path, runs_dir: Path) -> dict[str, Any]:
    parsed = parse_hint_markdown(_read_text(path))
    timestamp = _parse_datetime(parsed.get("generated_at")) or _fallback_timestamp(path)
    city_entries = parsed["cities"]

    suggestion_count = sum(len(city["candidate_additions"]) for city in city_entries)
    omitted_count = sum(len(city["omitted_projects"]) for city in city_entries)

    return {
        "name": path.name,
        "path": _run_relative_path(path, runs_dir),
        "url": f"/{_run_relative_path(path, runs_dir)}",
        "generated_at": timestamp.isoformat(),
        "summary_bullets": parsed["summary_bullets"],
        "summary_counts": parsed["summary_counts"],
        "city_count": len(city_entries),
        "suggestion_count": suggestion_count,
        "omitted_count": omitted_count,
        "cities": city_entries,
        "_sort_key": timestamp.timestamp(),
    }


def _build_report_card(path: Path, runs_dir: Path) -> dict[str, Any]:
    payload = _load_json(path)
    timestamp = _artifact_timestamp(payload, path)
    project_root = runs_dir.parent.resolve()
    city_reports = payload.get("city_reports") or []

    cities: list[dict[str, Any]] = []
    spotlight: list[dict[str, str | None]] = []

    for city_report in city_reports:
        if not isinstance(city_report, dict):
            continue

        accepted_projects = city_report.get("accepted_projects") or []
        rejected_candidates = city_report.get("rejected_candidates") or []
        cities.append(
            {
                "city": city_report.get("city") or "Unknown",
                "country": city_report.get("country") or "",
                "accepted": len(accepted_projects),
                "rejected": len(rejected_candidates),
            }
        )

        for project in accepted_projects:
            if not isinstance(project, dict) or len(spotlight) >= 6:
                continue
            spotlight.append(
                _project_snapshot(
                    project,
                    default_city=city_report.get("city") or "Unknown",
                    default_country=city_report.get("country") or "",
                )
            )

    review_path = _resolve_optional_path(payload.get("review_log_path"), project_root)
    hints_path = path.with_name(f"{path.stem}_hints.md")
    registry_path = _resolve_optional_path(payload.get("registry_path"), project_root)

    cities.sort(key=lambda item: (-item["accepted"], item["city"]))
    spotlight.sort(key=lambda item: item.get("_funding_sort", -1), reverse=True)

    return {
        "name": path.name,
        "path": _run_relative_path(path, runs_dir),
        "url": f"/{_run_relative_path(path, runs_dir)}",
        "generated_at": timestamp.isoformat(),
        "summary": payload.get("summary") or {},
        "city_count": len(cities),
        "cities": cities,
        "project_spotlight": _strip_project_internal_fields(spotlight),
        "registry": _run_link(registry_path, runs_dir),
        "review": _run_link(review_path, runs_dir),
        "hints": _run_link(hints_path if hints_path.exists() else None, runs_dir),
        "_sort_key": timestamp.timestamp(),
    }


def _build_summary_card(path: Path, runs_dir: Path) -> dict[str, Any]:
    payload = _load_json(path)
    timestamp = _artifact_timestamp(payload, path)
    project_root = runs_dir.parent.resolve()
    artifacts = payload.get("artifacts") or {}

    linked_artifacts: dict[str, dict[str, str] | None] = {}
    if isinstance(artifacts, dict):
        for key, target in artifacts.items():
            linked_artifacts[key] = _run_link(
                _resolve_optional_path(target if isinstance(target, str) else None, project_root),
                runs_dir,
            )

    cities = payload.get("cities") or []
    if isinstance(cities, list):
        cities = sorted(
            [city for city in cities if isinstance(city, dict)],
            key=lambda item: (-(item.get("accepted") or 0), item.get("city") or ""),
        )
    else:
        cities = []

    return {
        "name": path.name,
        "path": _run_relative_path(path, runs_dir),
        "url": f"/{_run_relative_path(path, runs_dir)}",
        "generated_at": timestamp.isoformat(),
        "summary": payload.get("summary") or {},
        "cities": cities,
        "artifacts": linked_artifacts,
        "_sort_key": timestamp.timestamp(),
    }


def _build_registry_card(path: Path, runs_dir: Path) -> dict[str, Any]:
    payload = _load_json(path)
    timestamp = _artifact_timestamp(payload, path)
    records = payload.get("records") or []

    city_counts: Counter[tuple[str, str]] = Counter()
    recent_records: list[dict[str, str | None]] = []
    active_count = 0
    active_records: list[dict[str, Any]] = []

    for record in records:
        if not isinstance(record, dict):
            continue
        city = record.get("city") or "Unknown"
        country = record.get("country") or ""
        city_counts[(city, country)] += 1
        if record.get("is_active"):
            active_count += 1
            active_records.append(record)
        recent_records.append(
            {
                "city": city,
                "country": country,
                "title": record.get("project_title") or "Untitled project",
                "last_verified_at": record.get("last_verified_at"),
                "source_url": (record.get("source_urls") or [None])[0],
            }
        )

    recent_records.sort(
        key=lambda item: _parse_datetime(item["last_verified_at"]) or datetime(1970, 1, 1, tzinfo=timezone.utc),
        reverse=True,
    )

    city_breakdown = [
        {"city": city, "country": country, "count": count}
        for (city, country), count in city_counts.most_common(12)
    ]

    funded_projects = [
        _project_snapshot(record)
        for record in active_records
        if _coerce_float(record.get("funding_amount")) is not None
    ]
    funded_projects.sort(key=lambda item: item.get("_funding_sort", -1), reverse=True)

    city_spend_focus_map: dict[tuple[str, str], dict[str, Any]] = {}
    currency_breakdown: Counter[str] = Counter()
    for item in funded_projects:
        currency_breakdown[item.get("currency") or "Unspecified"] += 1
        key = (str(item.get("city") or "Unknown"), str(item.get("country") or ""))
        current = city_spend_focus_map.get(key)
        if current is None:
            city_spend_focus_map[key] = {
                "city": item["city"],
                "country": item["country"],
                "disclosed_project_count": 1,
                "headline_amount": item.get("funding_display_short"),
                "headline_amount_full": item.get("funding_display"),
                "headline_project": item["title"],
                "what_city_is_buying": item["what_city_is_buying"],
                "funding_source": item.get("funding_source"),
                "funding_programme": item.get("funding_programme"),
                "climate_tags": item.get("climate_tags") or [],
                "source_url": item.get("source_url"),
                "_funding_sort": item.get("_funding_sort", -1),
            }
            continue

        current["disclosed_project_count"] += 1
        if item.get("_funding_sort", -1) > current.get("_funding_sort", -1):
            current.update(
                {
                    "headline_amount": item.get("funding_display_short"),
                    "headline_amount_full": item.get("funding_display"),
                    "headline_project": item["title"],
                    "what_city_is_buying": item["what_city_is_buying"],
                    "funding_source": item.get("funding_source"),
                    "funding_programme": item.get("funding_programme"),
                    "climate_tags": item.get("climate_tags") or [],
                    "source_url": item.get("source_url"),
                    "_funding_sort": item.get("_funding_sort", -1),
                }
            )

    city_spend_focus = sorted(
        city_spend_focus_map.values(),
        key=lambda item: item.get("_funding_sort", -1),
        reverse=True,
    )
    for item in city_spend_focus:
        item.pop("_funding_sort", None)

    return {
        "name": path.name,
        "path": _run_relative_path(path, runs_dir),
        "url": f"/{_run_relative_path(path, runs_dir)}",
        "generated_at": timestamp.isoformat(),
        "record_count": payload.get("record_count") or len(records),
        "active_count": active_count,
        "funded_project_count": len(funded_projects),
        "cities_with_funding_count": len(city_spend_focus),
        "city_breakdown": city_breakdown,
        "recent_records": recent_records[:8],
        "currency_breakdown": [
            {"currency": currency, "count": count}
            for currency, count in currency_breakdown.most_common(6)
        ],
        "top_funded_projects": _strip_project_internal_fields(funded_projects[:8]),
        "city_spend_focus": city_spend_focus[:12],
        "_sort_key": timestamp.timestamp(),
    }


def _strip_sort_key(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in items:
        shallow_copy = dict(item)
        shallow_copy.pop("_sort_key", None)
        cleaned.append(shallow_copy)
    return cleaned


def _report_summary_fallback(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if report is None:
        return None

    artifacts = {
        "report": {"path": report["path"], "url": report["url"]},
        "registry": report.get("registry"),
        "review": report.get("review"),
        "hints": report.get("hints"),
    }
    linked_artifacts = {key: value for key, value in artifacts.items() if value}

    return {
        "name": report["name"],
        "path": report["path"],
        "url": report["url"],
        "generated_at": report["generated_at"],
        "summary": report.get("summary") or {},
        "cities": report.get("cities") or [],
        "artifacts": linked_artifacts,
    }


def collect_dashboard(runs_dir: Path) -> dict[str, Any]:
    runs_dir = runs_dir.resolve()
    if not runs_dir.exists():
        raise FileNotFoundError(f"Run directory does not exist: {runs_dir}")

    report_cards: list[dict[str, Any]] = []
    summary_cards: list[dict[str, Any]] = []
    registry_cards: list[dict[str, Any]] = []
    hint_cards: list[dict[str, Any]] = []

    for path in sorted(runs_dir.iterdir()):
        if not path.is_file():
            continue

        if path.suffix == ".json" and "report" in path.stem:
            report_cards.append(_build_report_card(path, runs_dir))
            continue

        if path.suffix == ".json" and "summary" in path.stem:
            summary_cards.append(_build_summary_card(path, runs_dir))
            continue

        if path.suffix == ".json" and "registry" in path.stem:
            registry_cards.append(_build_registry_card(path, runs_dir))
            continue

        if path.suffix == ".md" and path.stem.endswith("_hints"):
            hint_cards.append(_build_hint_card(path, runs_dir))

    report_cards.sort(key=lambda item: item["_sort_key"], reverse=True)
    summary_cards.sort(key=lambda item: item["_sort_key"], reverse=True)
    registry_cards.sort(key=lambda item: item["_sort_key"], reverse=True)
    hint_cards.sort(key=lambda item: item["_sort_key"], reverse=True)

    recent_artifacts = sorted(
        [
            {"type": "report", **item}
            for item in report_cards[:6]
        ]
        + [
            {"type": "summary", **item}
            for item in summary_cards[:4]
        ]
        + [
            {"type": "registry", **item}
            for item in registry_cards[:4]
        ]
        + [
            {"type": "hints", **item}
            for item in hint_cards[:4]
        ],
        key=lambda item: item["_sort_key"],
        reverse=True,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs_directory": str(runs_dir),
        "artifact_counts": {
            "reports": len(report_cards),
            "summaries": len(summary_cards),
            "registries": len(registry_cards),
            "hints": len(hint_cards),
        },
        "latest_report": _strip_sort_key(report_cards[:1])[0] if report_cards else None,
        "latest_summary": (
            _strip_sort_key(summary_cards[:1])[0]
            if summary_cards
            else _report_summary_fallback(_strip_sort_key(report_cards[:1])[0] if report_cards else None)
        ),
        "latest_registry": _strip_sort_key(registry_cards[:1])[0] if registry_cards else None,
        "latest_reports": _strip_sort_key(report_cards[:6]),
        "latest_hints": _strip_sort_key(hint_cards[:4]),
        "recent_artifacts": _strip_sort_key(recent_artifacts[:12]),
    }
