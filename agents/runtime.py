from __future__ import annotations

import json
import logging
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import config

logger = logging.getLogger(__name__)

_VENDOR_READY = False


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_runtime_paths() -> None:
    global _VENDOR_READY
    if _VENDOR_READY:
        return

    vendor_wheels = config.PROJECT_ROOT / "vendor_wheels"
    sdk_wheel = vendor_wheels / "openai_agents-0.12.4-py3-none-any.whl"
    mcp_wheel = vendor_wheels / "mcp-1.26.0-py3-none-any.whl"
    firecrawl_wheel = vendor_wheels / "firecrawl_py-4.19.0-py3-none-any.whl"

    if mcp_wheel.exists():
        sys.path.insert(0, str(mcp_wheel))
    if sdk_wheel.exists():
        sys.path.insert(0, str(sdk_wheel))

    if firecrawl_wheel.exists():
        extract_dir = config.PROJECT_ROOT / ".vendor" / "firecrawl"
        sentinel = extract_dir / ".extracted"
        if not sentinel.exists():
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(firecrawl_wheel) as archive:
                archive.extractall(extract_dir)
            sentinel.write_text("ok", encoding="utf-8")
        sys.path.insert(0, str(extract_dir))

    _VENDOR_READY = True


def ensure_runs_dir() -> None:
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in clean:
        clean = clean.replace("--", "-")
    return clean.strip("-")


def load_prompt(prompt_name: str) -> str:
    prompt_path = Path(__file__).resolve().parent / "prompts" / prompt_name
    return prompt_path.read_text(encoding="utf-8")


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

