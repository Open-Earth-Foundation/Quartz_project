from __future__ import annotations

from html import unescape
import logging
import re
from io import BytesIO
from typing import Any
from urllib.parse import urljoin

import fitz
import requests

import config
from .runtime import ensure_runtime_paths
from .search import is_pdf_url, select_internal_links
from .types import CityTarget, ScrapedSource, SearchHit

logger = logging.getLogger(__name__)


class FirecrawlScraper:
    def __init__(self) -> None:
        ensure_runtime_paths()
        try:
            from firecrawl import Firecrawl  # type: ignore
        except Exception as exc:  # pragma: no cover - only used in live runs
            raise RuntimeError(f"Firecrawl import failed: {exc}") from exc

        self.client = Firecrawl(api_key=config.FIRECRAWL_API_KEY, api_url=config.FIRECRAWL_API_URL)

    def scrape_url(self, url: str) -> ScrapedSource | None:
        if is_pdf_url(url):
            return self._scrape_pdf(url)
        return self._scrape_html(url)

    def _scrape_html(self, url: str) -> ScrapedSource | None:
        try:
            document = self.client.scrape(
                url,
                formats=["markdown", "html", "links"],
                only_main_content=True,
                timeout=config.SCRAPE_TIMEOUT_SECONDS * 1000,
            )
            markdown = getattr(document, "markdown", "") or ""
            html = getattr(document, "html", "") or ""
            links = list(getattr(document, "links", []) or [])
            metadata = {}
            metadata_dict = getattr(document, "metadata_dict", None)
            if callable(metadata_dict):
                metadata = metadata_dict() or {}
            elif isinstance(metadata_dict, dict):
                metadata = metadata_dict
            elif getattr(document, "metadata", None):
                metadata = dict(document.metadata)
            title = metadata.get("title") or self._title_from_text(markdown)
            content = markdown or re.sub(r"\s+", " ", html)
            was_truncated = len(content) > config.MAX_INPUT_CHARS_PER_SOURCE
            return ScrapedSource(
                url=url,
                title=title or "",
                content=content[: config.MAX_INPUT_CHARS_PER_SOURCE],
                source_kind="html",
                internal_links=links,
                supporting_pdf_urls=[link for link in links if is_pdf_url(link)],
                metadata=metadata,
                was_truncated=was_truncated,
            )
        except Exception as exc:
            logger.warning("Firecrawl scrape failed for %s, falling back to raw fetch: %s", url, exc)
            return self._scrape_html_fallback(url)

    def _scrape_pdf(self, url: str) -> ScrapedSource:
        response = requests.get(url, timeout=config.SCRAPE_TIMEOUT_SECONDS)
        response.raise_for_status()
        document = fitz.open(stream=BytesIO(response.content), filetype="pdf")

        text_chunks: list[str] = []
        approx_tokens = 0
        for page in document:
            text = page.get_text("text").strip()
            if text:
                text_chunks.append(text)
                approx_tokens += max(len(text) // 4, 1)
            if approx_tokens >= config.PDF_TOKEN_LIMIT:
                break

        joined = "\n\n".join(text_chunks).strip()
        requires_ocr = not bool(joined)
        was_truncated = approx_tokens >= config.PDF_TOKEN_LIMIT
        return ScrapedSource(
            url=url,
            title=self._title_from_text(joined) or url.rsplit("/", 1)[-1],
            content=joined[: config.MAX_INPUT_CHARS_PER_SOURCE],
            source_kind="pdf",
            internal_links=[],
            supporting_pdf_urls=[url],
            metadata={},
            was_truncated=was_truncated,
            requires_ocr=requires_ocr,
        )

    def _scrape_html_fallback(self, url: str) -> ScrapedSource | None:
        response = requests.get(
            url,
            timeout=config.SCRAPE_TIMEOUT_SECONDS,
            headers={"User-Agent": "Quartz/1.0"},
        )
        response.raise_for_status()
        html = response.text
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        title = unescape(re.sub(r"\s+", " ", title_match.group(1))).strip() if title_match else ""
        links = self._extract_links(html, url)
        text = self._html_to_text(html)
        was_truncated = len(text) > config.MAX_INPUT_CHARS_PER_SOURCE
        return ScrapedSource(
            url=url,
            title=title or self._title_from_text(text),
            content=text[: config.MAX_INPUT_CHARS_PER_SOURCE],
            source_kind="html",
            internal_links=links,
            supporting_pdf_urls=[link for link in links if is_pdf_url(link)],
            metadata={"fetched_via": "raw_html_fallback"},
            was_truncated=was_truncated,
        )

    @staticmethod
    def _extract_links(html: str, base_url: str) -> list[str]:
        links: list[str] = []
        for match in re.finditer(r"""href=["']([^"'#]+)["']""", html, flags=re.IGNORECASE):
            href = match.group(1).strip()
            if href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            links.append(urljoin(base_url, href))
        deduped: list[str] = []
        seen: set[str] = set()
        for link in links:
            if link not in seen:
                seen.add(link)
                deduped.append(link)
        return deduped

    @staticmethod
    def _html_to_text(html: str) -> str:
        cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
        cleaned = re.sub(r"(?i)</(p|div|section|article|li|h1|h2|h3|h4|h5|h6|br)>", "\n", cleaned)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = unescape(cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def _title_from_text(text: str) -> str:
        for line in text.splitlines():
            clean = line.strip().lstrip("#").strip()
            if len(clean) >= 5:
                return clean
        return ""

    def collect_sources(self, city_target: CityTarget, hits: list[SearchHit]) -> list[ScrapedSource]:
        collected: list[ScrapedSource] = []
        seen_urls: set[str] = set()
        queue = [hit.url for hit in hits]

        while queue and len(collected) < config.MAX_DOCUMENTS_PER_CITY:
            url = queue.pop(0)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            try:
                source = self.scrape_url(url)
            except Exception as exc:  # pragma: no cover - exercised in live canary
                logger.warning("Scrape failed for %s: %s", url, exc)
                continue
            if source is None:
                continue
            collected.append(source)
            if source.source_kind == "html":
                for link in select_internal_links(source.internal_links, city_target, source.url):
                    if link not in seen_urls:
                        queue.append(link)
                for pdf_link in source.supporting_pdf_urls[:2]:
                    if pdf_link not in seen_urls:
                        queue.append(pdf_link)
        return collected
