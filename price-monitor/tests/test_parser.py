from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from price_monitor.parser import (
    build_session,
    decode_response_text,
    parse_catalogue,
    parse_price,
    scrape_catalogue,
)

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_URL = "https://books.toscrape.com/catalogue/page-1.html"


def test_parse_catalogue_fixture_without_network() -> None:
    html = (FIXTURES / "catalogue_page.html").read_text(encoding="utf-8")
    products, next_url = parse_catalogue(html, PAGE_URL)

    assert next_url == "https://books.toscrape.com/catalogue/page-2.html"
    assert [item.title for item in products] == [
        "A Light in the Attic",
        "Tipping the Velvet",
        "Soumission",
    ]
    attic = products[0]
    assert attic.price == Decimal("51.77")
    assert attic.currency == "GBP"
    assert attic.availability == "In stock"
    assert attic.in_stock is True
    assert attic.rating == 3
    assert attic.url == (
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    )
    assert products[1].rating == 1
    assert products[2].in_stock is False
    assert products[2].rating == 5
    assert products[2].price == Decimal("50.10")


def test_parse_price_currency_and_thousands() -> None:
    assert parse_price("£51.77") == (Decimal("51.77"), "GBP")
    assert parse_price("£1,234.50") == (Decimal("1234.50"), "GBP")
    assert parse_price("Â£51.77") == (Decimal("51.77"), "GBP")
    assert parse_price("$9.99") == (Decimal("9.99"), "USD")
    assert parse_price("€10.00") == (Decimal("10.00"), "EUR")


def test_decode_response_uses_utf8_when_charset_is_missing() -> None:
    class _Response:
        def __init__(self) -> None:
            self.content = "£51.77".encode()
            self.headers = {"Content-Type": "text/html"}
            self.encoding = "ISO-8859-1"

        @property
        def apparent_encoding(self) -> str:
            return "utf-8"

        @property
        def text(self) -> str:
            return self.content.decode(self.encoding)

    assert decode_response_text(_Response()) == "£51.77"


def test_session_sets_user_agent_and_retries() -> None:
    session = build_session(user_agent="PortfolioBot/1.0", retries=5, backoff_factor=0.2)
    try:
        assert session.headers["User-Agent"] == "PortfolioBot/1.0"
        retry = session.get_adapter("https://books.toscrape.com/").max_retries
        assert retry.total == 5
        assert retry.backoff_factor == 0.2
        assert 429 in retry.status_forcelist
        assert 503 in retry.status_forcelist
    finally:
        session.close()


class _Response:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _Pages:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.calls: list[str] = []
        self.closed = False

    def get(self, url: str, timeout: float = 20) -> _Response:
        self.calls.append(url)
        if url not in self.pages:
            raise AssertionError(f"unexpected url {url}")
        return _Response(self.pages[url])

    def close(self) -> None:
        self.closed = True


def test_scrape_follows_pagination_and_stops_at_max_pages() -> None:
    page_1 = (FIXTURES / "catalogue_page.html").read_text(encoding="utf-8")
    page_2 = (FIXTURES / "catalogue_page_2.html").read_text(encoding="utf-8")
    session = _Pages(
        {
            PAGE_URL: page_1,
            "https://books.toscrape.com/catalogue/page-2.html": page_2,
        }
    )
    products = scrape_catalogue(PAGE_URL, max_pages=2, session=session, delay_seconds=0)
    assert [item.title for item in products] == [
        "A Light in the Attic",
        "Tipping the Velvet",
        "Soumission",
        "Sharp Objects",
    ]
    assert products[3].rating == 4
    assert products[3].price == Decimal("47.82")
    assert session.calls == [
        PAGE_URL,
        "https://books.toscrape.com/catalogue/page-2.html",
    ]
    assert session.closed is False


def test_scrape_rejects_non_positive_max_pages() -> None:
    with pytest.raises(ValueError):
        scrape_catalogue(PAGE_URL, max_pages=0, session=_Pages({}))
