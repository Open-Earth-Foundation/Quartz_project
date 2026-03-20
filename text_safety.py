from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

PDF_TEXT_MARKERS = ("%pdf-", "endobj", "endstream", "startxref", "%%eof", "/type/catalog")


def looks_like_binary_document_text(value: str | None) -> bool:
    sample = re.sub(r"\s+", " ", str(value or "")).strip()[:800]
    if not sample:
        return False

    lowered = sample.casefold()
    if lowered.startswith(PDF_TEXT_MARKERS[0]):
        return True

    marker_hits = sum(marker in lowered for marker in PDF_TEXT_MARKERS[1:])
    control_chars = sum(1 for char in sample if ord(char) < 32 and char not in "\t\n\r")
    replacement_chars = sample.count("\ufffd")
    return marker_hits >= 2 or control_chars > 0 or replacement_chars >= 8


def fallback_document_title(url: str | None = None) -> str:
    if not url:
        return "PDF document"

    parsed = urlparse(url)
    filename = unquote(parsed.path.rsplit("/", 1)[-1]).strip()
    if filename and "." in filename and filename.casefold() not in {"download"}:
        stem = filename.rsplit(".", 1)[0]
        cleaned = re.sub(r"[-_]+", " ", stem).strip()
        if cleaned:
            return cleaned

    domain = parsed.netloc.lower().removeprefix("www.")
    if domain:
        return f"PDF document from {domain}"
    return "PDF document"


def sanitize_display_title(title: str | None, url: str | None = None) -> str:
    cleaned = re.sub(r"\s+", " ", str(title or "")).strip(" -|")
    if not cleaned or looks_like_binary_document_text(cleaned):
        return fallback_document_title(url)
    return cleaned
