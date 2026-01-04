#!/usr/bin/env python3
"""Example fetcher stub for funded city climate projects."""
from __future__ import annotations

import json


def fetch() -> list[dict]:
    """Return a tiny mocked dataset showing required fields + funding authority."""
    return [
        {
            "project_name": "Demo Green Roofs",
            "city": "Demo City",
            "country": "Demo Land",
            "funding_status": "funded",
            "funding_amount": 2500000,
            "funding_currency": "USD",
            "funding_source": "Demo City Council",
            "approval_date": "2022-04-15",
            "source_url": "https://example.org/demo-green-roofs",
            "funding_authority": "city",
        }
    ]


def main() -> None:
    print(json.dumps(fetch(), indent=2))


if __name__ == "__main__":
    main()
