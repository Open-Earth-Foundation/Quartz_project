from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
RUNS_DIR = PROJECT_ROOT / "runs"
DEFAULT_CITIES_FILE = PROJECT_ROOT / "NZC.json"
DEFAULT_REGISTRY_FILE = RUNS_DIR / "city_project_registry.json"
DEFAULT_RUN_REPORT_FILE = RUNS_DIR / "last_run_report.json"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")
HTTP_REFERER = os.getenv("HTTP_REFERER", "https://github.com/piotr/Quartz_project")
SITE_NAME = os.getenv("SITE_NAME", "Quartz City Climate Registry")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_API_URL = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev")

DEFAULT_TIMEOUT_SECONDS = int(os.getenv("QUARTZ_TIMEOUT_SECONDS", "45"))
SCRAPE_TIMEOUT_SECONDS = int(os.getenv("QUARTZ_SCRAPE_TIMEOUT_SECONDS", "15"))
MAX_DISCOVERY_QUERIES = int(os.getenv("QUARTZ_MAX_DISCOVERY_QUERIES", "6"))
MAX_RESULTS_PER_QUERY = int(os.getenv("QUARTZ_MAX_RESULTS_PER_QUERY", "5"))
MAX_SOURCE_URLS_PER_CITY = int(os.getenv("QUARTZ_MAX_SOURCE_URLS_PER_CITY", "6"))
MAX_INTERNAL_LINKS_PER_SOURCE = int(os.getenv("QUARTZ_MAX_INTERNAL_LINKS_PER_SOURCE", "6"))
MAX_DOCUMENTS_PER_CITY = int(os.getenv("QUARTZ_MAX_DOCUMENTS_PER_CITY", "8"))
MAX_INPUT_CHARS_PER_SOURCE = int(os.getenv("QUARTZ_MAX_INPUT_CHARS_PER_SOURCE", "22000"))
PDF_TOKEN_LIMIT = int(os.getenv("QUARTZ_PDF_TOKEN_LIMIT", "100000"))

DISCOVERY_AGENT_TEMPERATURE = float(os.getenv("QUARTZ_DISCOVERY_TEMPERATURE", "0.1"))
VERIFICATION_AGENT_TEMPERATURE = float(os.getenv("QUARTZ_VERIFICATION_TEMPERATURE", "0.0"))

ENABLE_SDK = os.getenv("QUARTZ_DISABLE_SDK", "").strip().lower() not in {"1", "true", "yes"}
ENABLE_LIVE_CANARY = os.getenv("QUARTZ_ENABLE_LIVE_CANARY", "").strip().lower() in {"1", "true", "yes"}

OFFICIAL_DOMAIN_MARKERS = (
    ".gov",
    "gov.",
    "bip.",
    "um.",
    "miasto",
    "city",
    "municipal",
    "municipality",
    "metropolia",
    "public",
)

LOW_TRUST_DOMAIN_MARKERS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "reddit.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "wikipedia.org",
)

ACTIVE_STATUS_HINTS = (
    "active",
    "ongoing",
    "in implementation",
    "in progress",
    "under construction",
    "underway",
    "open",
    "current",
    "realizacja",
    "w trakcie",
    "trwa",
    "kontynu",
)

INACTIVE_STATUS_HINTS = (
    "completed",
    "finished",
    "cancelled",
    "closed",
    "historical",
    "archive",
    "zakończ",
    "ukończ",
    "anulow",
)

FUNDING_HINTS = (
    "funded",
    "funding",
    "co-financed",
    "cofinanced",
    "financed",
    "grant",
    "budget",
    "investment",
    "programme",
    "program",
    "dofinansowanie",
    "dofinansowany",
    "dotacja",
    "finansowanie",
    "środki",
)

CLIMATE_HINTS = (
    "climate",
    "emission",
    "energy",
    "mobility",
    "transport",
    "adaptation",
    "resilience",
    "air quality",
    "heat",
    "green",
    "renewable",
    "efficiency",
    "waste",
    "water",
    "stormwater",
    "retention",
    "solar",
    "district heating",
    "rower",
    "powietrze",
    "klimat",
    "adaptac",
    "energi",
    "transport",
    "retenc",
)
