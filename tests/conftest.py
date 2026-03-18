from __future__ import annotations

import os

from bootstrap_local_agents import load_local_agents_package

os.environ["QUARTZ_DISABLE_SDK"] = "1"

load_local_agents_package()
