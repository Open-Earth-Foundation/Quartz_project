from __future__ import annotations

from quartz_agents.search import classify_source_confidence, normalize_domain, rank_hit
from quartz_agents.types import CityTarget, SearchHit


CITY = CityTarget(
    city="Warsaw",
    country="Poland",
    aliases=["Warszawa"],
    seed_domains=["um.warszawa.pl", "eko.um.warszawa.pl"],
)


def test_city_root_domain_is_city_root():
    confidence = classify_source_confidence("https://um.warszawa.pl/green-project", CITY, "Green Project", "")
    assert confidence == "city_root"


def test_extra_seed_domain_is_municipal_entity_not_city_root():
    confidence = classify_source_confidence(
        "https://eko.um.warszawa.pl/projekty/zielone-enklawy",
        CITY,
        "Green enclaves",
        "Municipal climate adaptation project.",
    )
    assert confidence == "municipal_entity"


def test_root_subdomain_is_city_subdomain():
    confidence = classify_source_confidence(
        "https://bip.um.warszawa.pl/waw/bip/projekty",
        CITY,
        "City projects",
        "Official municipal publication.",
    )
    assert confidence == "city_subdomain"


def test_non_seed_municipal_domain_is_municipal_entity():
    confidence = classify_source_confidence(
        "https://bip.transport.warszawa.pl/inwestycje/tramwaj",
        CITY,
        "Miejska inwestycja",
        "Urząd miasta Warszawy",
    )
    assert confidence == "municipal_entity"


def test_low_trust_domain_is_reject_external():
    confidence = classify_source_confidence("https://reddit.com/r/warsaw", CITY, "thread", "random discussion")
    assert confidence == "reject_external"


def test_external_domain_with_city_mentions_stays_supporting():
    confidence = classify_source_confidence(
        "https://www.interreg-central.eu/projects/example",
        CITY,
        "Warsaw project page",
        "Municipality of Warsaw participates in the project.",
    )
    assert confidence == "supporting_external"


def test_demoted_government_domain_stays_supporting_external():
    confidence = classify_source_confidence(
        "https://www.gov.pl/web/feniks/warsaw-project",
        CITY,
        "Programme Environment, Energy and Climate Change",
        "Warsaw municipality is a beneficiary.",
    )
    assert confidence == "supporting_external"


def test_news_domain_with_city_name_is_not_treated_as_municipal():
    city = CityTarget(city="Gdansk", country="Poland", aliases=["Gdańsk"], seed_domains=["gdansk.pl"])
    confidence = classify_source_confidence(
        "https://radiogdansk.pl/wiadomosci/2026/01/13/fundacja-orlen-dla-pomorza-przyznala-granty-na-rzecz-adaptacji-klimatycznej/",
        city,
        "Fundacja Orlen dla Pomorza przyznała granty",
        "Gdańsk and the region received grants for climate adaptation.",
    )
    assert confidence == "supporting_external"


def test_non_city_subdomain_under_city_tld_is_not_treated_as_city_subdomain():
    city = CityTarget(city="Lodz", country="Poland", aliases=["Łódź"], seed_domains=["uml.lodz.pl", "lodz.pl"])
    confidence = classify_source_confidence(
        "https://www.wfosigw.lodz.pl/programy/czyste-powietrze/komunikaty-ogloszenia/",
        city,
        "Program Priorytetowy Czyste Powietrze",
        "Funding programme information page.",
    )
    assert confidence == "supporting_external"


def test_preferred_path_prefix_is_ranked_above_generic_city_news():
    preferred = SearchHit(
        query="Warsaw climate",
        url="https://um.warszawa.pl/waw/europa/-/zielone-enklawy-dzielnicy-praga-poludnie",
        title="Zielone enklawy dzielnicy Praga-Południe",
        snippet="Projekt dofinansowany i realizowany",
    )
    generic = SearchHit(
        query="Warsaw climate",
        url="https://um.warszawa.pl/aktualnosci/miasto-i-klimat",
        title="Miasto i klimat",
        snippet="Ogólna aktualność miejska",
    )
    assert rank_hit(preferred, CITY) > rank_hit(generic, CITY)


def test_invalid_url_normalization_is_safe():
    assert normalize_domain("http://[broken") == ""
