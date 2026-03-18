from __future__ import annotations

from io import BytesIO

import fitz

from quartz_agents.scrape import FirecrawlScraper


class DummyResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def _make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    return doc.tobytes()


def test_pdf_text_is_extracted(monkeypatch):
    scraper = object.__new__(FirecrawlScraper)
    monkeypatch.setattr("quartz_agents.scrape.requests.get", lambda *args, **kwargs: DummyResponse(_make_pdf_bytes("LIFE funded adaptation project ongoing")))
    source = scraper._scrape_pdf("https://example.org/project.pdf")
    assert source.source_kind == "pdf"
    assert "LIFE funded" in source.content
    assert source.requires_ocr is False


def test_pdf_without_text_is_flagged_for_ocr(monkeypatch):
    scraper = object.__new__(FirecrawlScraper)
    monkeypatch.setattr("quartz_agents.scrape.requests.get", lambda *args, **kwargs: DummyResponse(_make_pdf_bytes("")))
    source = scraper._scrape_pdf("https://example.org/scan.pdf")
    assert source.requires_ocr is True
    assert source.supporting_pdf_urls == ["https://example.org/scan.pdf"]

