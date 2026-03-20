from __future__ import annotations

from io import BytesIO

import fitz

from quartz_agents.scrape import FirecrawlScraper


class DummyResponse:
    def __init__(self, content: bytes, headers: dict[str, str] | None = None) -> None:
        self.content = content
        self.headers = headers or {}

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


def test_pdf_download_endpoint_is_detected_without_pdf_extension(monkeypatch):
    scraper = object.__new__(FirecrawlScraper)
    scraper.client = None
    monkeypatch.setattr(
        "quartz_agents.scrape.requests.get",
        lambda *args, **kwargs: DummyResponse(
            _make_pdf_bytes("Climate city contract and funded adaptation project"),
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": 'attachment; filename="commitment-plan.pdf"',
            },
        ),
    )
    source = scraper.scrape_url("https://example.org/download?id=123")
    assert source is not None
    assert source.source_kind == "pdf"
    assert "Climate city contract" in source.content
    assert source.supporting_pdf_urls == ["https://example.org/download?id=123"]
