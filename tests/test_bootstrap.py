from __future__ import annotations

from bootstrap_local_agents import load_local_agents_package


def test_local_agents_package_loads_under_alias():
    module = load_local_agents_package()
    assert module.__name__ == "quartz_agents"


def test_sdk_bridge_loads_official_sdk_package():
    from quartz_agents.sdk_bridge import get_sdk

    sdk = get_sdk()
    assert sdk.Agent is not None
    assert sdk.Runner is not None

