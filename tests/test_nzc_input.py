from __future__ import annotations

import json
from pathlib import Path

from quartz_agents.types import CityBatchInput


def test_nzc_json_is_rich_default_input():
    payload = json.loads(Path("NZC.json").read_text(encoding="utf-8"))
    batch = CityBatchInput.model_validate(payload)
    assert [city.city for city in batch.cities] == ["Krakow", "Warsaw", "Gdansk"]
    assert batch.cities[0].aliases == ["Kraków"]

