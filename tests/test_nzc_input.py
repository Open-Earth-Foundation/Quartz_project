from __future__ import annotations

import json
from pathlib import Path

from quartz_agents.types import CityBatchInput


def test_nzc_json_matches_current_mission_city_targets():
    payload = json.loads(Path("NZC.json").read_text(encoding="utf-8"))
    batch = CityBatchInput.model_validate(payload)
    assert len(batch.cities) == 111
    assert any(city.city == "Eindhoven & Helmond" for city in batch.cities)

    warsaw = next(city for city in batch.cities if city.city == "Warsaw")
    krakow = next(city for city in batch.cities if city.city == "Kraków")
    wroclaw = next(city for city in batch.cities if city.city == "Wrocław")
    amsterdam = next(city for city in batch.cities if city.city == "Amsterdam")
    eindhoven_helmond = next(city for city in batch.cities if city.city == "Eindhoven & Helmond")

    assert warsaw.aliases == ["Warszawa"]
    assert warsaw.seed_domains[0] == "um.warszawa.pl"
    assert krakow.aliases == ["Krakow"]
    assert wroclaw.aliases == ["Wroclaw"]
    assert eindhoven_helmond.seed_domains[:2] == ["eindhoven.nl", "helmond.nl"]
    assert "social.amsterdam.nl" not in amsterdam.seed_domains
    assert "werkenbij.amsterdam.nl" not in amsterdam.seed_domains
