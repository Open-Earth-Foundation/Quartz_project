"""
Configuration module for loading environment variables.
"""

import os
from dotenv import load_dotenv
from typing import Optional, Any, Dict, List
import toml  # Import the toml library

# Load environment variables from .env file
load_dotenv()

# --- API Keys (from .env) ---
FIRECRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID: str = os.getenv("GOOGLE_CSE_ID", "")

# --- Load settings from TOML file ---
DEFAULT_SETTINGS_FILE = "settings.toml"


def load_toml_settings(settings_file: str = DEFAULT_SETTINGS_FILE) -> Dict[str, Any]:
    """Loads settings from a TOML file."""
    try:
        with open(settings_file, "r") as f:
            return toml.load(f)
    except FileNotFoundError:
        print(
            f"Warning: Settings file '{settings_file}' not found. Using default values where applicable."
        )
        return {}
    except toml.TomlDecodeError:
        print(
            f"Error: Could not decode TOML from '{settings_file}'. Check for syntax errors."
        )
        return {}


_toml_settings = load_toml_settings()

# --- General Settings ---
APP_NAME: str = _toml_settings.get("general", {}).get(
    "app_name", "Quartz City Climate Projects Finder"
)
APP_VERSION: str = _toml_settings.get("general", {}).get("version", "2.1.0")
PROJECT_GOAL: str = _toml_settings.get("general", {}).get(
    "project_goal",
    "Use Quartz to find city climate projects that were funded or fully implemented in the last 20 years.",
)

# --- Funding Scope Settings ---
FUNDED_LOOKBACK_YEARS: int = int(
    _toml_settings.get("funding_scope", {}).get("lookback_years", 20)
)
ENABLE_FUNDED_PROJECT_FLOW: bool = bool(
    _toml_settings.get("funding_scope", {}).get("enable_funded_project_flow", True)
)
ENABLE_FUNDING_FILTER_LOG: bool = bool(
    _toml_settings.get("funding_scope", {}).get("enable_funding_filter_log", True)
)
ACCEPTED_FUNDED_STATUSES: List[str] = _toml_settings.get("funding_scope", {}).get(
    "accepted_statuses",
    ["approved", "in_implementation", "completed", "funded"],
)

# --- Search Mode Settings ---
DEFAULT_SEARCH_MODE: str = _toml_settings.get("search", {}).get(
    "default_search_mode", "funded_projects"
)  # "ghgi_data" or "funded_projects"

# --- Search Settings ---
MAX_RESULTS_PER_QUERY: int = _toml_settings.get("search", {}).get(
    "max_results_per_query", 10
)
MAX_PAGES_PER_DOMAIN: int = _toml_settings.get("search", {}).get(
    "max_pages_per_domain", 5
)
MAX_SEARCHES_PER_RUN: int = _toml_settings.get("agent", {}).get(
    "max_searches_per_run", 50
)
MAX_ADDITIONAL_EXPANSION_QUERIES: int = _toml_settings.get("search", {}).get(
    "max_additional_expansion_queries", 3
)
MAX_TOTAL_SEARCHES: int = _toml_settings.get("search", {}).get("max_total_searches", 30)
MAX_GOOGLE_QUERIES_PER_RUN: int = int(
    _toml_settings.get("search", {}).get(
        "max_google_queries_per_run", os.getenv("MAX_GOOGLE_QUERIES_PER_RUN", 50)
    )
)

# --- Model Settings ---
THINKING_MODEL: str = _toml_settings.get("models", {}).get(
    "thinking_model", "anthropic/claude-haiku-4.5"
)
NORMAL_MODEL: str = _toml_settings.get("models", {}).get(
    "normal_model", "anthropic/claude-haiku-4.5"
)
STRUCTURED_MODEL: str = _toml_settings.get("models", {}).get(
    "structured_model", "anthropic/claude-haiku-4.5"
)
STRUCTURED_MODEL_THINKING: str = _toml_settings.get("models", {}).get(
    "structured_model_for_review", "anthropic/claude-haiku-4.5"
)
RELEVANCE_CHECK_MODEL: Optional[str] = _toml_settings.get("models", {}).get(
    "relevance_check_model", "anthropic/claude-haiku-4.5"
)
DEFAULT_TEMPERATURE: float = _toml_settings.get("models", {}).get(
    "default_temperature", 0.2
)
MAX_TOKENS: int = _toml_settings.get("models", {}).get("max_tokens", 100000)

# --- OpenRouter API specific configuration (still from .env for base URL, but could be toml) ---
OPENROUTER_BASE_URL: str = os.getenv(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)
HTTP_REFERER: str = os.getenv("HTTP_REFERER", "https://github.com/automatic_research")
SITE_NAME: str = os.getenv("SITE_NAME", "GHGI Dataset Discovery Agent")

# --- Retry Settings ---
MAX_RETRY_ATTEMPTS: int = _toml_settings.get("retry", {}).get("max_attempts", 3)
BASE_RETRY_DELAY: float = _toml_settings.get("retry", {}).get("base_delay", 5.0)
MAX_RETRY_DELAY: float = _toml_settings.get("retry", {}).get("max_delay", 60.0)

# --- Scraping Settings ---
CONCURRENT_SCRAPE_LIMIT: int = _toml_settings.get("scraping", {}).get(
    "concurrent_scrape_limit", 4
)

# --- Agent Settings ---
MAX_ITERATIONS: int = _toml_settings.get("agent", {}).get("max_iterations", 10)
MAX_DEEP_DIVES: int = _toml_settings.get("agent", {}).get(
    "max_deep_dives", 5
)  # This is for consecutive deep dives triggered by reviewer
MAX_ACTIONS_PER_DEEP_DIVE_CYCLE: int = _toml_settings.get("agent", {}).get(
    "max_actions_per_deep_dive_cycle", 15
)  # Max actions (scrape/search) within one deep dive directive
ENABLE_PRE_SCRAPE_RELEVANCE_CHECK: bool = _toml_settings.get("agent", {}).get(
    "enable_pre_scrape_relevance_check", True
)

# === ADDED: Reviewer Node Specific Settings ===
MAX_REVIEWER_SNIPPET_LENGTH: int = _toml_settings.get("agent", {}).get(
    "max_reviewer_snippet_length", 5000
)
MAX_DOCS_FOR_REVIEW: int = _toml_settings.get("agent", {}).get(
    "max_docs_for_review", 15
)
# === END ADDED ===

# --- Storage Settings ---
OUTPUT_DIR: str = _toml_settings.get("storage", {}).get("output_dir", "runs")
FILENAME_FORMAT: str = _toml_settings.get("storage", {}).get(
    "filename_format", "results_%s.json"
)
FUNDED_REPORT_DIR: str = _toml_settings.get("storage", {}).get(
    "funded_report_dir", "runs/funded_reports"
)


# --- Validate required API keys ---
def validate_api_keys() -> dict[str, bool]:
    """
    Validate that required API keys are set.
    Returns a dictionary with the validation status of each key.
    """
    return {
        "firecrawl": bool(FIRECRAWL_API_KEY),
        "openrouter": bool(OPENROUTER_API_KEY),
    }


# Add new configuration for researcher cycles
MAX_QUERIES_PER_RESEARCH_CYCLE = (
    MAX_SEARCHES_PER_RUN  # Use same value as MAX_SEARCHES_PER_RUN
)
