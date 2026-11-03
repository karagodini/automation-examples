from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from price_monitor.models import Product

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "automation-examples-price-monitor/1.0 "
    "(+https://github.com/karagodini/automation-examples; portfolio demo)"
)

DEFAULT_CATALOGUE_URL = "https://books.toscrape.com/catalogue/page-1.html"

_RATING_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


class SupportsGet(Protocol):
    def get(self, url: str, timeout: float = 20) -> Any: ...

    def close(self) -> None: ...


def build_session(
    user_agent: str = DEFAULT_USER_AGENT,
    retries: int = 3,
    backoff_factor: float = 0.5,
) -> requests.Session:
    """Сессия с User-Agent и повторами на сетевые ошибки и ответы 429/5xx."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en",
        }
    )
    return session


def parse_price(raw: str) -> tuple[Decimal, str]:
    # Â£ / Â€ — фунт и евро, если UTF-8 прочитали как Latin-1.
    text = raw.strip().replace("\xa0", "").replace("Â£", "£").replace("Â€", "€")
    if "£" in text:
        currency = "GBP"
    elif "€" in text:
        currency = "EUR"
    elif "$" in text:
        currency = "USD"
    else:
        currency = "GBP"
    cleaned = text.replace("£", "").replace("€", "").replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned), currency
    except InvalidOperation as exc:
        raise ValueError(f"Не удалось разобрать цену: {raw!r}") from exc


def parse_rating(class_names: list[str]) -> int:
    for name in class_names:
        rating = _RATING_WORDS.get(name.lower())
        if rating is not None:
            return rating
    return 0


def parse_catalogue(html: str, page_url: str) -> tuple[list[Product], str | None]:
    """Достаёт товары и ссылку на следующую страницу из HTML каталога."""
    soup = BeautifulSoup(html, "html.parser")
    products: list[Product] = []
    for article in soup.select("article.product_pod"):
        title_link = article.select_one("h3 a")
        if title_link is None:
            continue
        title = (title_link.get("title") or title_link.get_text() or "").strip()
        href = str(title_link.get("href") or "")
        price_node = article.select_one("p.price_color")
        price_raw = price_node.get_text(strip=True) if price_node else ""
        price, currency = parse_price(price_raw) if price_raw else (Decimal("0"), "GBP")
        availability_node = article.select_one("p.availability")
        if availability_node is None:
            availability = ""
        else:
            availability = " ".join(availability_node.get_text(" ", strip=True).split())
        rating_node = article.select_one("p.star-rating")
        class_names = (
            [str(name) for name in (rating_node.get("class") or [])] if rating_node else []
        )
        products.append(
            Product(
                title=title,
                price=price,
                currency=currency,
                availability=availability,
                in_stock="in stock" in availability.lower(),
                rating=parse_rating(class_names),
                url=urljoin(page_url, href),
            )
        )

    next_link = soup.select_one("li.next a")
    next_href = str(next_link.get("href")) if next_link and next_link.get("href") else ""
    next_url = urljoin(page_url, next_href) if next_href else None
    return products, next_url


def decode_response_text(response: Any) -> str:
    """Декодирует HTML. У books.toscrape.com нет charset, и requests выбирает Latin-1."""
    headers = getattr(response, "headers", None)
    content_type = ""
    if headers is not None and hasattr(headers, "get"):
        content_type = str(headers.get("Content-Type") or headers.get("content-type") or "")
    apparent = getattr(response, "apparent_encoding", None)
    encoding = str(getattr(response, "encoding", None) or "").lower()
    charset_missing = "charset" not in content_type.lower()
    guessed_latin = encoding in {"", "iso-8859-1", "latin-1"}
    if apparent and charset_missing and guessed_latin:
        response.encoding = apparent
    return str(response.text)


def fetch_html(session: SupportsGet, url: str, timeout: float = 20.0) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return decode_response_text(response)


def scrape_catalogue(
    start_url: str,
    *,
    max_pages: int = 1,
    session: SupportsGet | None = None,
    timeout: float = 20.0,
    delay_seconds: float = 0.0,
) -> list[Product]:
    """Обходит каталог по ссылке next, не больше max_pages страниц."""
    if max_pages < 1:
        raise ValueError("max_pages должен быть не меньше 1")
    own_session = session is None
    http: SupportsGet = session or build_session()
    products: list[Product] = []
    seen_urls: set[str] = set()
    url: str | None = start_url
    pages = 0
    try:
        while url and pages < max_pages:
            if pages and delay_seconds > 0:
                time.sleep(delay_seconds)
            logger.info("Загрузка %s", url)
            html = fetch_html(http, url, timeout=timeout)
            page_products, next_url = parse_catalogue(html, url)
            for product in page_products:
                if product.url in seen_urls:
                    continue
                seen_urls.add(product.url)
                products.append(product)
            pages += 1
            url = next_url
    finally:
        if own_session:
            http.close()
    return products
