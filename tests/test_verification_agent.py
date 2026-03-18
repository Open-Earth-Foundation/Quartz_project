from __future__ import annotations

from types import MethodType

from quartz_agents.types import CityTarget, ScrapedSource
from quartz_agents.verification_agent import VerificationAgent


def test_verification_accepts_funded_municipal_tram_project():
    agent = VerificationAgent()
    city = CityTarget(city="Krakow", country="Poland", aliases=["Kraków"], seed_domains=["krakow.pl"])
    source = ScrapedSource(
        url="https://ue.krakow.pl/aktualnosci/starowislna",
        title="Umowa o dofinansowanie przebudowy torowiska w ul. Starowiślnej podpisana. - Oficjalny serwis miejski - Magiczny Kraków",
        content="""
        Przebudowa torowiska tramwajowego w ulicy Starowiślnej uzyskała wraz z zawartą umową o dofinansowanie
        środki unijne z Programu Fundusze Europejskie na Infrastrukturę, Klimat, Środowisko.
        Mieszkańcy Krakowa otrzymają ponad 2 km zmodernizowanych linii tramwajowych i ścieżki rowerowe.
        Przebudowa wpłynie na ograniczenie liczby podróży transportem indywidualnym i poprawę jakości powietrza.
        Dofinansowanie: 82 650 406,50 zł.
        """,
    )

    result = agent._verify_with_heuristics(city, source, "city_root")

    assert len(result.accepted_projects) == 1
    project = result.accepted_projects[0]
    assert project.project_title == "Umowa o dofinansowanie przebudowy torowiska w ul. Starowiślnej podpisana."
    assert "mobility" in project.climate_tags
    assert "air_quality" in project.climate_tags
    assert project.funding_amount == 82650406.50


def test_verification_rejects_programme_page_without_real_climate_project_signal():
    agent = VerificationAgent()
    city = CityTarget(city="Krakow", country="Poland", aliases=["Kraków"], seed_domains=["krakow.pl"])
    source = ScrapedSource(
        url="https://ma.krakow.pl/feniks/",
        title="FEnIKS - Fundusze Europejskie na Infrastrukturę, Klimat, Środowisko - Muzeum Archeologiczne w Krakowie",
        content="""
        Zarządzaj zgodami plików cookie.
        Używamy plików cookie by witryna internetowa działała prawidłowo.
        Muzeum Archeologiczne w Krakowie otrzymało dofinansowanie z Programu Fundusze Europejskie na Infrastrukturę,
        Klimat, Środowisko 2021-2027 na realizację projektu modernizacji obiektu.
        """,
    )

    result = agent._verify_with_heuristics(city, source, "municipal_entity")

    assert not result.accepted_projects
    assert result.rejected_candidates
    assert any(
        marker in result.rejected_candidates[0].reason
        for marker in ("missing climate signal", "generic landing page", "generic funding-programme page")
    )


def test_verification_rejects_generic_landing_page():
    agent = VerificationAgent()
    city = CityTarget(city="Krakow", country="Poland", aliases=["Kraków"], seed_domains=["krakow.pl"])
    source = ScrapedSource(
        url="https://ue.krakow.pl/",
        title="Unijne Oblicze Krakowa - Oficjalny serwis miejski - Magiczny Kraków",
        content="Portal z wieloma projektami i aktualnościami o funduszach europejskich.",
    )

    result = agent._verify_with_heuristics(city, source, "city_root")

    assert not result.accepted_projects
    assert "generic landing page" in result.rejected_candidates[0].reason


def test_verification_rejects_event_update_page():
    agent = VerificationAgent()
    city = CityTarget(city="Warsaw", country="Poland", aliases=["Warszawa"], seed_domains=["um.warszawa.pl"])
    source = ScrapedSource(
        url="https://um.warszawa.pl/waw/europa/-/spotkanie-projektu",
        title="Spotkanie międzynarodowego projektu MECOG-CE w Berlinie - Europejska Warszawa",
        content="Projekt uzyskał dofinansowanie z Interreg, a partnerzy spotkali się w Berlinie.",
    )

    result = agent._verify_with_heuristics(city, source, "city_root")

    assert not result.accepted_projects
    assert "event/update page" in result.rejected_candidates[0].reason


def test_verification_rejects_summary_page_before_sdk_like_extraction():
    agent = VerificationAgent()
    city = CityTarget(city="Gdynia", country="Poland", aliases=[], seed_domains=["gdynia.pl"])
    source = ScrapedSource(
        url="https://www.gdynia.pl/mieszkaniec/gdynia-mobilna,7582/zrownowazona-mobilnosc-i-transport-podsumowanie-2023-roku,578449",
        title="Zrównoważona mobilność i transport - podsumowanie 2023 roku",
        content="Projekt otrzymał dofinansowanie, ale strona jest tylko podsumowaniem wielu działań miasta.",
    )

    result = agent._verify_with_heuristics(city, source, "city_root")

    assert not result.accepted_projects
    assert "summary/report page" in result.rejected_candidates[0].reason


def test_verification_rejects_generic_report_pdf():
    agent = VerificationAgent()
    city = CityTarget(city="Szczecin", country="Poland", aliases=[], seed_domains=["szczecin.eu", "szczecin.pl"])
    source = ScrapedSource(
        url="https://bip.um.szczecin.pl/files/E798001CF30D4B01B32A3D9B2DFC2F22/000-2022-raportostanieGMS.pdf",
        title="Raport o stanie Gminy Miasto Szczecin",
        content="Raport zawiera inwestycje i dofinansowanie w wielu obszarach.",
        source_kind="pdf",
    )

    result = agent._verify_with_heuristics(city, source, "city_subdomain")

    assert not result.accepted_projects
    assert "summary/report page" in result.rejected_candidates[0].reason


def test_verification_rejects_profile_page_even_on_city_domain():
    agent = VerificationAgent()
    city = CityTarget(city="Gdynia", country="Poland", aliases=[], seed_domains=["gdynia.pl"])
    source = ScrapedSource(
        url="https://www.gdynia.pl/team/anna-kowalska",
        title="Anna Kowalska - climate team",
        content="Projekt otrzymał dofinansowanie i dotyczy klimatu.",
    )

    result = agent._verify_with_heuristics(city, source, "city_root")

    assert not result.accepted_projects
    assert "profile or category page" in result.rejected_candidates[0].reason


def test_verification_rejects_supporting_external_as_final_source():
    agent = VerificationAgent()
    city = CityTarget(city="Poznan", country="Poland", aliases=["Poznań"], seed_domains=["poznan.pl"])
    source = ScrapedSource(
        url="https://put.poznan.pl/scientific-projects/green-campus",
        title="Scientific projects - Green Campus",
        content="The project received funding and supports the climate transition.",
    )

    result = agent._verify_with_heuristics(city, source, "supporting_external")

    assert not result.accepted_projects
    assert "needs municipal confirmation" in result.rejected_candidates[0].reason


def test_sdk_source_class_aliases_are_normalized():
    agent = VerificationAgent()
    assert agent._normalize_source_class("official", fallback="municipal_entity") == "city_root"
    assert agent._normalize_source_class("high", fallback="municipal_entity") == "city_root"
    assert agent._normalize_source_class("external", fallback="city_root") == "supporting_external"
    assert agent._normalize_source_class("unknown_label", fallback="municipal_entity") == "municipal_entity"


def test_sdk_payload_plausibility_rejects_generic_social_extraction():
    agent = VerificationAgent()
    source = ScrapedSource(
        url="https://um.warszawa.pl/-/cztery-nowe-projekty-z-unijnym-wsparciem",
        title="Cztery nowe projekty z unijnym wsparciem - Miasto Warszawa",
        content="",
    )

    assert not agent._sdk_payload_is_plausible(
        {
            "project_title": "Nowa przestrzeń społeczna w m.st. Warszawie",
            "summary": "Projekt społeczny współfinansowany ze środków UE.",
            "climate_tags": ["adaptation"],
            "funding_source": "UE",
            "funding_programme": "FEnIKS",
            "funding_amount": None,
            "funding_evidence": "współfinansowany ze środków UE",
        },
        source,
    )


def test_sdk_payload_plausibility_accepts_specific_transport_project():
    agent = VerificationAgent()
    source = ScrapedSource(
        url="https://um.warszawa.pl/waw/europa/-/budowa-ii-linii-metra-etap-iv",
        title="Budowa II linii metra etap IV - Europejska Warszawa",
        content="",
    )

    assert agent._sdk_payload_is_plausible(
        {
            "project_title": "Budowa II linii metra etap IV",
            "summary": "Projekt transportu publicznego współfinansowany z FEnIKS, ograniczający emisje z transportu.",
            "climate_tags": ["mobility", "air_quality"],
            "funding_source": "UE",
            "funding_programme": "FEnIKS",
            "funding_amount": 1000000.0,
            "funding_evidence": "współfinansowany z FEnIKS",
        },
        source,
    )


async def test_verify_source_falls_back_to_heuristics_when_sdk_returns_only_rejections(monkeypatch):
    agent = VerificationAgent()
    city = CityTarget(city="Lodz", country="Poland", aliases=["Łódź"], seed_domains=["uml.lodz.pl"])
    source = ScrapedSource(
        url="https://uml.lodz.pl/ekoportal/klimat/powietrze/program-czyste-powietrze/",
        title="Program Czyste Powietrze",
        content="""
        Program Czyste Powietrze otrzymał dofinansowanie i jest realizowany na rzecz poprawy jakości powietrza.
        Miasto Łódź prowadzi działania w ramach programu, a nabór trwa.
        """,
    )

    async def fake_sdk(*_args, **_kwargs):
        from quartz_agents.types import RejectedCandidate, VerificationResult

        return VerificationResult(
            source_class="city_root",
            accepted_projects=[],
            rejected_candidates=[
                RejectedCandidate(
                    url=source.url,
                    title=source.title,
                    source_class="city_root",
                    reason="SDK extraction lacked a specific climate/funding signal for a final registry record.",
                    borderline=True,
                )
            ],
        )

    monkeypatch.setattr("quartz_agents.verification_agent.sdk_available", lambda: True)
    agent._verify_with_sdk = MethodType(fake_sdk, agent)

    result = await agent.verify_source(city, source)

    assert result.accepted_projects
    assert result.accepted_projects[0].project_title == "Program Czyste Powietrze"
