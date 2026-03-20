from __future__ import annotations

from quartz_agents.scrape import FirecrawlScraper


class DummyHtmlResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


def test_html_fallback_extracts_text_and_links(monkeypatch):
    scraper = object.__new__(FirecrawlScraper)
    html = """
    <html>
      <head><title>City Project Portal</title></head>
      <body>
        <h1>Green Tram Line</h1>
        <p>Municipal climate project with grant funding in progress.</p>
        <a href="/projects/tram-extension">Project page</a>
        <a href="https://example.org/files/award.pdf">Award PDF</a>
      </body>
    </html>
    """
    monkeypatch.setattr("quartz_agents.scrape.requests.get", lambda *args, **kwargs: DummyHtmlResponse(html))
    source = scraper._scrape_html_fallback("https://city.example.org/transport")

    assert source is not None
    assert source.title == "City Project Portal"
    assert "Green Tram Line" in source.content
    assert "grant funding in progress" in source.content
    assert "https://city.example.org/projects/tram-extension" in source.internal_links
    assert source.supporting_pdf_urls == ["https://example.org/files/award.pdf"]
    assert source.metadata["fetched_via"] == "raw_html_fallback"


def test_scraper_init_falls_back_when_firecrawl_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        FirecrawlScraper,
        "_build_firecrawl_client",
        lambda self: (_ for _ in ()).throw(RuntimeError("No module named 'websockets'")),
    )

    scraper = FirecrawlScraper()

    assert scraper.client is None
    assert "websockets" in scraper.firecrawl_error
