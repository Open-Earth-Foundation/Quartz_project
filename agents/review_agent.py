from __future__ import annotations

from urllib.parse import urlparse

from .city_hints import CityHintEntry, path_matches_hints, resolve_city_hints
from .runtime import now_utc_iso
from .search import CITY_ECOSYSTEM_CLASSES, LOW_VALUE_TITLE_PATTERNS, LOW_VALUE_URL_PATTERNS, classify_source_class, normalize_domain
from .types import BatchRunReport, CityTarget, RejectedCandidate, SearchHit, VerifiedProject, normalize_city_key

PROJECT_KEYWORDS = (
    "feniks",
    "life",
    "dofinans",
    "grant",
    "tram",
    "tramwaj",
    "metro",
    "oze",
    "ciepłe mieszkanie",
    "retenc",
    "kanaliz",
    "waste",
    "adapt",
    "food wave",
    "co-adapt",
    "gozilla",
    "neest",
    "rewitaliz",
)


class ReviewAgent:
    def build_hints_markdown(self, batch_report: BatchRunReport, city_targets: list[CityTarget]) -> str:
        target_by_city = {normalize_city_key(target.city): target for target in city_targets}
        lines = ["# Hint Suggestions", ""]
        lines.append(f"Generated at: {now_utc_iso()}")
        lines.append("")
        lines.append("## Summary")
        lines.append(
            f"- accepted={sum(len(city.accepted_projects) for city in batch_report.city_reports)}, "
            f"rejected={batch_report.summary.rejected}"
        )
        lines.append("- This file is advisory. It does not modify the maintained city hint registry automatically.")
        lines.append("")

        for city_report in batch_report.city_reports:
            target = target_by_city[normalize_city_key(city_report.city)]
            hints = resolve_city_hints(target)
            accepted_urls = {url for project in city_report.accepted_projects for url in project.source_urls}
            suspicious = self._suspicious_accepted(city_report.accepted_projects, target, hints)
            omissions = self._likely_omissions(city_report.search_hits, city_report.rejected_candidates, accepted_urls, target, hints)
            additions = self._hint_additions(city_report.search_hits, omissions, target, hints)
            demotions = self._demotion_suggestions(city_report.search_hits, city_report.rejected_candidates, hints)

            lines.append(f"## {city_report.city}, {city_report.country}")
            lines.append("")
            lines.append("### Candidate Hint Additions")
            if additions:
                for item in additions:
                    lines.append(f"- {item}")
            else:
                lines.append("- None")
            lines.append("")
            lines.append("### Candidate Demotions")
            if demotions:
                for item in demotions:
                    lines.append(f"- {item}")
            else:
                lines.append("- None")
            lines.append("")
            lines.append("### Likely Omitted Official/Municipal Projects")
            if omissions:
                for title, url, reason in omissions:
                    lines.append(f"- {title} | {url} | {reason}")
            else:
                lines.append("- None")
            lines.append("")
            lines.append("### Suspicious Accepted Records")
            if suspicious:
                for title, url, reason in suspicious:
                    lines.append(f"- {title} | {url} | {reason}")
            else:
                lines.append("- None")
            lines.append("")
        return "\n".join(lines)

    def _suspicious_accepted(
        self,
        accepted_projects: list[VerifiedProject],
        city_target: CityTarget,
        hints: CityHintEntry,
    ) -> list[tuple[str, str, str]]:
        findings: list[tuple[str, str, str]] = []
        known_domains = set(hints.city_root_domains + hints.preferred_domains + hints.municipal_domains)
        for project in accepted_projects:
            url = project.source_urls[0]
            domain = normalize_domain(url)
            title = project.project_title.casefold()
            lowered_url = url.casefold()
            if project.source_class not in CITY_ECOSYSTEM_CLASSES:
                findings.append((project.project_title, url, "accepted from non-city ecosystem source"))
                continue
            if domain and domain not in known_domains and not any(domain.endswith(f".{root}") for root in hints.city_root_domains):
                findings.append((project.project_title, url, "domain is not currently in the city hint ecosystem"))
                continue
            if any(token in title for token in ("home", "city of", "sdg", "eurocities", "c40", "strategy", "information centre for foreigners")):
                findings.append((project.project_title, url, "title looks like a generic page, not a concrete project"))
                continue
            if any(token in lowered_url for token in LOW_VALUE_URL_PATTERNS):
                findings.append((project.project_title, url, "URL pattern looks like profile/category content"))
        return findings

    def _likely_omissions(
        self,
        search_hits: list[SearchHit],
        rejected_candidates: list[RejectedCandidate],
        accepted_urls: set[str],
        city_target: CityTarget,
        hints: CityHintEntry,
    ) -> list[tuple[str, str, str]]:
        omissions: list[tuple[str, str, str]] = []

        for hit in search_hits:
            if hit.url in accepted_urls:
                continue
            source_class = hit.source_class or classify_source_class(hit.url, city_target, hit.title, hit.snippet)
            if source_class not in CITY_ECOSYSTEM_CLASSES:
                continue
            lowered = f"{hit.title} {hit.snippet} {hit.url}".casefold()
            if any(pattern in lowered for pattern in LOW_VALUE_TITLE_PATTERNS + LOW_VALUE_URL_PATTERNS):
                continue
            if not any(keyword in lowered for keyword in PROJECT_KEYWORDS):
                continue
            reason_bits = []
            if path_matches_hints(hit.url, hints):
                reason_bits.append("matches preferred path")
            if any(fragment in lowered for fragment in hints.preferred_query_fragments):
                reason_bits.append("matches preferred fragment")
            if "dofinans" in lowered or "funded" in lowered or "feniks" in lowered:
                reason_bits.append("strong funding signal")
            omissions.append((hit.title or hit.url, hit.url, ", ".join(reason_bits) or "official-looking hit worth review"))

        for item in rejected_candidates:
            if item.url in accepted_urls:
                continue
            if item.source_class not in CITY_ECOSYSTEM_CLASSES:
                continue
            lowered = f"{item.title} {item.reason} {item.url}".casefold()
            if any(token in lowered for token in ("missing funding signal", "missing climate signal", "missing active signal")) and any(
                keyword in lowered for keyword in PROJECT_KEYWORDS
            ):
                omissions.append((item.title or item.url, item.url, f"borderline rejection: {item.reason}"))

        deduped: list[tuple[str, str, str]] = []
        seen_urls: set[str] = set()
        for item in omissions:
            if item[1] in seen_urls:
                continue
            seen_urls.add(item[1])
            deduped.append(item)
        return deduped[:6]

    def _hint_additions(
        self,
        search_hits: list[SearchHit],
        omissions: list[tuple[str, str, str]],
        city_target: CityTarget,
        hints: CityHintEntry,
    ) -> list[str]:
        suggestions: list[str] = []
        known_domains = set(hints.city_root_domains + hints.preferred_domains + hints.municipal_domains)
        for _, url, _ in omissions:
            domain = normalize_domain(url)
            if domain and domain not in known_domains:
                suggestions.append(f"domain: {domain}")
            prefix = self._suggest_path_prefix(url)
            if prefix and prefix not in hints.preferred_path_prefixes:
                suggestions.append(f"path_prefix: {prefix}")
        for hit in search_hits:
            lowered = f"{hit.title} {hit.snippet}".casefold()
            for keyword in ("feniks", "metro", "tramwaj", "tram", "oze", "ciepłe mieszkanie", "co-adapt", "food wave", "rewitalizacja", "kanaliz"):
                if keyword in lowered and keyword not in hints.preferred_query_fragments:
                    suggestions.append(f"query_fragment: {keyword}")
        return self._dedupe(suggestions)[:8]

    def _demotion_suggestions(
        self,
        search_hits: list[SearchHit],
        rejected_candidates: list[RejectedCandidate],
        hints: CityHintEntry,
    ) -> list[str]:
        suggestions: list[str] = []
        known_domains = set(hints.city_root_domains + hints.preferred_domains + hints.municipal_domains)
        for hit in search_hits:
            domain = normalize_domain(hit.url)
            lowered = f"{hit.title} {hit.url}".casefold()
            if (
                hit.source_class == "supporting_external"
                and domain
                and domain not in hints.demoted_domains
                and domain not in known_domains
            ):
                if any(token in lowered for token in ("university", "unesco", "akcjamiasto", "gov.pl", "interreg")):
                    suggestions.append(f"domain: {domain}")
            for pattern in LOW_VALUE_URL_PATTERNS:
                if pattern in lowered and pattern not in hints.demoted_url_patterns:
                    suggestions.append(f"url_pattern: {pattern}")
        for item in rejected_candidates:
            domain = normalize_domain(item.url)
            lowered = f"{item.title} {item.reason} {item.url}".casefold()
            if (
                domain
                and domain not in known_domains
                and any(token in lowered for token in ("profile", "category", "generic national funding page"))
            ):
                suggestions.append(f"domain: {domain}")
            for pattern in LOW_VALUE_URL_PATTERNS:
                if pattern in lowered and pattern not in hints.demoted_url_patterns:
                    suggestions.append(f"url_pattern: {pattern}")
        return self._dedupe(suggestions)[:8]

    @staticmethod
    def _suggest_path_prefix(url: str) -> str | None:
        parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
        if not parts:
            return None
        prefix = "/" + "/".join(parts[: min(2, len(parts))])
        if len(prefix) < 4:
            return None
        return prefix.casefold()

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped
