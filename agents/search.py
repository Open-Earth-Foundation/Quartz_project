from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

import config
from .city_hints import path_matches_hints, resolve_city_hints, url_matches_demotions
from .types import CityTarget, SearchHit, SourceClass

logger = logging.getLogger(__name__)

CITY_ECOSYSTEM_CLASSES: tuple[SourceClass, ...] = ("city_root", "city_subdomain", "municipal_entity")
LOW_VALUE_TITLE_PATTERNS = ("spotkanie", "meeting", "newsletter", "conference", "workshop", "seminar", "home", "information centre")
LOW_VALUE_URL_PATTERNS = ("/category/", "/tag/", "?team=", "/team/", "/author/", "/profile/")
ACADEMIC_DOMAIN_MARKERS = ("edu", ".ac.", "unesco", "pan.pl", "put.poznan.pl", "up.poznan.pl", "ue.poznan.pl")
NON_MUNICIPAL_DOMAIN_MARKERS = (
    "radio",
    "gazeta",
    "dziennik",
    "akcjamiasto",
    "wfos",
    "nfos",
    "interreg",
    "funduszeeuropejskie",
    "fundacja",
    "wbpp",
    "orlen",
)


def normalize_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def is_pdf_url(url: str) -> bool:
    return url.lower().split("?")[0].endswith(".pdf")


def classify_source_class(
    url: str,
    city_target: CityTarget,
    title: str = "",
    text: str = "",
) -> SourceClass:
    domain = normalize_domain(url)
    hints = resolve_city_hints(city_target)
    haystack = f"{title} {text} {url}".casefold()

    if not domain or any(marker in domain for marker in config.LOW_TRUST_DOMAIN_MARKERS):
        return "reject_external"
    if any(marker in domain for marker in NON_MUNICIPAL_DOMAIN_MARKERS):
        return "supporting_external"
    if url_matches_demotions(url, hints):
        return "supporting_external"
    if any(domain == demoted or domain.endswith(f".{demoted}") for demoted in hints.demoted_domains):
        return "supporting_external"
    if domain == "gov.pl" or domain.endswith(".gov.pl"):
        return "supporting_external"
    if any(marker in domain for marker in ACADEMIC_DOMAIN_MARKERS):
        return "supporting_external"

    root_domains = set(hints.city_root_domains)
    preferred_domains = set(hints.preferred_domains)
    municipal_domains = set(hints.municipal_domains)

    if domain in municipal_domains or any(domain.endswith(f".{municipal}") for municipal in municipal_domains):
        return "municipal_entity"
    if domain in root_domains:
        return "city_root"
    if any(domain.endswith(f".{root}") for root in root_domains):
        return "city_subdomain"
    if domain in preferred_domains:
        return "municipal_entity"
    if any(domain.endswith(f".{preferred}") for preferred in preferred_domains):
        return "municipal_entity"

    normalized_domain = domain.replace("-", ".")
    if (
        any(name.casefold().replace(" ", "") in normalized_domain.replace(".", "") for name in city_target.names)
        and any(marker in normalized_domain for marker in config.OFFICIAL_DOMAIN_MARKERS)
    ):
        return "municipal_entity"
    return "supporting_external"


def classify_source_confidence(
    url: str,
    city_target: CityTarget,
    title: str = "",
    text: str = "",
) -> SourceClass:
    return classify_source_class(url, city_target, title, text)


def rank_hit(hit: SearchHit, city_target: CityTarget) -> float:
    hints = resolve_city_hints(city_target)
    source_class = classify_source_class(hit.url, city_target, hit.title, hit.snippet)
    hit.source_class = source_class
    confidence_score = {
        "city_root": 6,
        "city_subdomain": 5,
        "municipal_entity": 4,
        "supporting_external": 1,
        "reject_external": -4,
    }[source_class]
    keyword_score = 0
    haystack = f"{hit.title} {hit.snippet}".lower()
    title = hit.title.lower()
    lowered_url = hit.url.lower()
    path = urlparse(hit.url).path.strip("/")
    for keyword in (*config.FUNDING_HINTS, *config.CLIMATE_HINTS):
        if keyword in haystack:
            keyword_score += 0.35
    if any(
        token in haystack
        for token in ("project", "projekt", "life", "zeroemission", "zero emission", "tram", "tramwaj", "retention", "powietrz", "solar", "feniks", "oze", "rewitaliz", "metro")
    ):
        keyword_score += 1.1
    if path_matches_hints(hit.url, hints):
        keyword_score += 2.2
    if any(fragment in haystack for fragment in hints.preferred_query_fragments):
        keyword_score += 1.2
    if any(token in title for token in LOW_VALUE_TITLE_PATTERNS):
        keyword_score -= 1.5
    if (not path or path.count("/") < 1) and any(
        token in title for token in ("unijne oblicze", "fundusze europejskie", "europejska warszawa", "projekty", "portal")
    ):
        keyword_score -= 1.5
    if any(token in lowered_url for token in LOW_VALUE_URL_PATTERNS):
        keyword_score -= 2.2
    if title.startswith("program ") or "program priorytetowy" in title:
        keyword_score -= 0.8
    if url_matches_demotions(hit.url, hints):
        keyword_score -= 3
    if is_pdf_url(hit.url):
        keyword_score += 0.5
    return confidence_score + keyword_score


class GoogleSearchClient:
    def search(self, query: str, city_target: CityTarget) -> list[SearchHit]:
        if not config.GOOGLE_API_KEY or not config.GOOGLE_CSE_ID:
            logger.warning("Google Custom Search credentials are missing; returning no hits.")
            return []

        response = requests.get(
            config.GOOGLE_SEARCH_URL,
            params={
                "key": config.GOOGLE_API_KEY,
                "cx": config.GOOGLE_CSE_ID,
                "q": query,
                "num": min(config.MAX_RESULTS_PER_QUERY, 10),
            },
            timeout=config.DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()

        results: list[SearchHit] = []
        for item in payload.get("items", []):
            hit = SearchHit(
                query=query,
                url=item.get("link", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
            )
            hit.rank_score = rank_hit(hit, city_target)
            results.append(hit)
        return results


def dedupe_and_rank_hits(hits: list[SearchHit], city_target: CityTarget) -> list[SearchHit]:
    best_by_url: dict[str, SearchHit] = {}
    for hit in hits:
        hit.rank_score = rank_hit(hit, city_target)
        current = best_by_url.get(hit.url)
        if current is None or hit.rank_score > current.rank_score:
            best_by_url[hit.url] = hit
    ranked = sorted(best_by_url.values(), key=lambda item: item.rank_score, reverse=True)
    return ranked[: config.MAX_SOURCE_URLS_PER_CITY]


def select_internal_links(links: list[str], city_target: CityTarget, parent_url: str) -> list[str]:
    parent_domain = normalize_domain(parent_url)
    hints = resolve_city_hints(city_target)
    selected: list[str] = []
    for link in links:
        domain = normalize_domain(link)
        if not domain:
            continue
        link_class = classify_source_class(link, city_target)
        if url_matches_demotions(link, hints):
            continue
        if domain != parent_domain and link_class not in CITY_ECOSYSTEM_CLASSES:
            continue
        lowered = link.lower()
        if path_matches_hints(link, hints) or re.search(r"(projekt|project|inwest|climate|klimat|fund|dofinans|adapt|energy|transport|mobility|waste|water|tram|metro|oze|rewitaliz)", lowered):
            selected.append(link)
    deduped: list[str] = []
    seen: set[str] = set()
    for link in selected:
        if link not in seen:
            seen.add(link)
            deduped.append(link)
    return deduped[: config.MAX_INTERNAL_LINKS_PER_SOURCE]
