from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from .types import CityTarget


class CityHintEntry(BaseModel):
    city_root_domains: list[str] = Field(default_factory=list)
    preferred_domains: list[str] = Field(default_factory=list)
    municipal_domains: list[str] = Field(default_factory=list)
    preferred_path_prefixes: list[str] = Field(default_factory=list)
    preferred_query_fragments: list[str] = Field(default_factory=list)
    demoted_domains: list[str] = Field(default_factory=list)
    demoted_url_patterns: list[str] = Field(default_factory=list)


DEFAULT_CITY_HINTS: dict[str, CityHintEntry] = {
    "krakow": CityHintEntry(
        city_root_domains=["krakow.pl"],
        preferred_domains=["kegw.krakow.pl", "ue.krakow.pl", "convention.krakow.pl", "ziw.krakow.pl"],
        preferred_path_prefixes=["/krakow_open_city/", "/klimat/", "/fundusze_europejskie/", "/aktualnosci/"],
        preferred_query_fragments=["umowa o dofinansowanie", "FEnIKS", "klimat", "tramwaj", "NEEST"],
        demoted_domains=["wfos.krakow.pl", "acciona.com", "funduszeeuropejskie.gov.pl"],
        demoted_url_patterns=["/programy/", "mały strażak", "bezpieczny strażak", "edukacja ekologiczna"],
    ),
    "warsaw": CityHintEntry(
        city_root_domains=["um.warszawa.pl"],
        preferred_domains=["eko.um.warszawa.pl", "en.um.warszawa.pl"],
        municipal_domains=["transport.warszawa.pl", "targowek.um.warszawa.pl"],
        preferred_path_prefixes=["/waw/europa/", "/waw/eko/", "/zywnosc-i-klimat", "/-/zagraj-w-gre-i-zmien-klimat-na-lepsze"],
        preferred_query_fragments=["umowa o dofinansowanie", "FEnIKS", "metro", "zielone enklawy", "co-adapt", "food wave"],
        demoted_domains=["interreg-central.eu", "gov.pl"],
        demoted_url_patterns=["/spotkanie-", "/meeting", "/newsletter", "/conference"],
    ),
    "gdansk": CityHintEntry(
        city_root_domains=["gdansk.pl"],
        preferred_domains=["media.gdansk.pl", "czystemiasto.gdansk.pl"],
        municipal_domains=["download.cloudgdansk.pl"],
        preferred_path_prefixes=["/wiadomosci/", "/komunikaty/", "/en/life-pom-gozilla-pl"],
        preferred_query_fragments=["tramwaj", "FEnIKS", "LIFE", "GOZilla", "dofinansowanie"],
        demoted_domains=["wfos.gdansk.pl"],
        demoted_url_patterns=["budżet obywatelski"],
    ),
    "wroclaw": CityHintEntry(
        city_root_domains=["wroclaw.pl"],
        preferred_domains=["zielony-wroclaw.wroclaw.pl", "www.wroclaw.pl"],
        preferred_path_prefixes=["/zielony-wroclaw/", "/zielony-wroclaw/budujemy-klimat"],
        preferred_query_fragments=["budujemy klimat", "adaptacji klimatycznej", "tramwaj", "dofinansowanie"],
        demoted_domains=["akcjamiasto.org", "gov.pl"],
        demoted_url_patterns=["/energy-projects"],
    ),
    "lodz": CityHintEntry(
        city_root_domains=["uml.lodz.pl", "lodz.pl"],
        preferred_domains=["mci.uml.lodz.pl"],
        preferred_path_prefixes=["/ekoportal/", "/projekty-z-dofinansowaniem/"],
        preferred_query_fragments=["łódzkie szkoły dla klimatu", "odtwarzanie siedlisk", "FEnIKS", "NEEST", "ciepłe powietrze"],
        demoted_domains=["erce.unesco.lodz.pl"],
        demoted_url_patterns=["/version-", "/mops/"],
    ),
    "poznan": CityHintEntry(
        city_root_domains=["poznan.pl"],
        preferred_domains=["mpk.poznan.pl"],
        preferred_path_prefixes=["/mim/main/fundusze-europejskie", "/mim/info/news/", "/mim/komunikacja/news"],
        preferred_query_fragments=["FEnIKS", "tramwaj", "dofinansowanie", "zieleń", "projekt dofinansowany"],
        demoted_domains=["put.poznan.pl", "ue.poznan.pl", "up.poznan.pl", "wfosgw.poznan.pl"],
        demoted_url_patterns=["proland", "scientific-projects"],
    ),
    "katowice": CityHintEntry(
        city_root_domains=["katowice.eu"],
        preferred_domains=["17celow.katowice.eu"],
        preferred_path_prefixes=["/dla-mieszkańca/miejskie-centrum-energii/", "/dla-mieszka%C5%84ca/miejskie-centrum-energii/"],
        preferred_query_fragments=["OZE", "miejskie centrum energii", "dofinansowanie", "ekologiczny transport"],
        demoted_url_patterns=["strategia", "business infrastructure"],
    ),
    "lublin": CityHintEntry(
        city_root_domains=["lublin.eu"],
        preferred_path_prefixes=["/mieszkancy/srodowisko/", "/lublin/przestrzen-miejska/rewitalizacja/"],
        preferred_query_fragments=["ciepłe mieszkanie", "rewitalizacja", "dofinansowanie", "powietrze"],
        demoted_domains=["funduszeeuropejskie.lubelskie.pl"],
        demoted_url_patterns=["urszulanki", "nabory"],
    ),
    "gdynia": CityHintEntry(
        city_root_domains=["gdynia.pl"],
        preferred_domains=["klimat.um.gdynia.pl"],
        municipal_domains=["port.gdynia.pl", "pewik.gdynia.pl"],
        preferred_path_prefixes=["/ue/trwajace", "/mieszkaniec/gdynia-mobilna", "/mieszkaniec/co-nowego"],
        preferred_query_fragments=["FEnIKS", "mobilność", "kanalizacyjnej", "oczyszczalni", "we make transition"],
        demoted_domains=["mir.gdynia.pl"],
        demoted_url_patterns=["?team=", "hackathon", "urbanlab"],
    ),
    "szczecin": CityHintEntry(
        city_root_domains=["szczecin.eu", "szczecin.pl"],
        preferred_domains=["wiadomosci.szczecin.eu"],
        preferred_path_prefixes=["/pl/zielone-miasto/", "/artykul/komunikacja/", "/artykul/gospodarka-odpadami/"],
        preferred_query_fragments=["ZEFIREK", "ekologiczny transport", "dofinansowanie", "odpady"],
        demoted_domains=["feniks.gov.pl"],
        demoted_url_patterns=["/category/living-in-szczecin/", "life in poland", "partnership for culture"],
    ),
}


def _unique(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


@lru_cache(maxsize=None)
def get_city_hints(city_key: str) -> CityHintEntry:
    return DEFAULT_CITY_HINTS.get(city_key.casefold(), CityHintEntry())


def resolve_city_hints(city_target: CityTarget) -> CityHintEntry:
    base = get_city_hints(city_target.city)
    return CityHintEntry(
        city_root_domains=_unique(base.city_root_domains + city_target.seed_domains),
        preferred_domains=_unique(base.preferred_domains + city_target.seed_domains),
        municipal_domains=_unique(base.municipal_domains),
        preferred_path_prefixes=_unique(base.preferred_path_prefixes),
        preferred_query_fragments=_unique(base.preferred_query_fragments),
        demoted_domains=_unique(base.demoted_domains),
        demoted_url_patterns=_unique(base.demoted_url_patterns),
    )


def path_matches_hints(url: str, hint_entry: CityHintEntry) -> bool:
    path = urlparse(url).path.casefold()
    return any(prefix and path.startswith(prefix) for prefix in hint_entry.preferred_path_prefixes)


def url_matches_demotions(url: str, hint_entry: CityHintEntry) -> bool:
    lowered = url.casefold()
    return any(pattern and pattern in lowered for pattern in hint_entry.demoted_url_patterns)
