from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlparse

import requests

from price_monitor.diff import CatalogueDiff, PriceChange
from price_monitor.models import Product

_MAX_ITEMS = 15
_MAX_CHARS = 3900


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def _stock_label(product: Product) -> str:
    return "в наличии" if product.in_stock else "нет в наличии"


def _percent(change: PriceChange) -> str:
    if change.old_price == 0:
        return ""
    percent = (change.delta / change.old_price) * Decimal(100)
    return f" ({percent:+.1f}%)"


def _product_block(product: Product) -> list[str]:
    return [
        (
            f"• {product.title} — {_money(product.price)} {product.currency}, "
            f"{_stock_label(product)}, рейтинг {product.rating}/5"
        ),
        f"  {product.url}",
    ]


def _change_block(change: PriceChange) -> list[str]:
    product = change.product
    return [
        (
            f"• {product.title} — {_money(change.old_price)} → {_money(change.new_price)} "
            f"{product.currency}{_percent(change)}"
        ),
        f"  {product.url}",
    ]


def format_diff_message(diff: CatalogueDiff, *, source_url: str, checked: int) -> str:
    host = urlparse(source_url).netloc or source_url
    lines = [
        f"Мониторинг цен — {host}",
        f"Источник: {source_url}",
        f"Проверено позиций: {checked}",
        f"Новых товаров: {len(diff.new_products)}",
        f"Изменения цен: {len(diff.price_changes)}",
    ]
    if diff.new_products:
        lines.append("")
        lines.append("Новые товары:")
        shown = diff.new_products[:_MAX_ITEMS]
        for product in shown:
            lines.extend(_product_block(product))
        hidden = len(diff.new_products) - len(shown)
        if hidden:
            lines.append(f"… и ещё {hidden}")
    if diff.price_changes:
        lines.append("")
        lines.append("Изменения цен:")
        shown_changes = diff.price_changes[:_MAX_ITEMS]
        for change in shown_changes:
            lines.extend(_change_block(change))
        hidden = len(diff.price_changes) - len(shown_changes)
        if hidden:
            lines.append(f"… и ещё {hidden}")
    text = "\n".join(lines)
    if len(text) <= _MAX_CHARS:
        return text
    return text[: _MAX_CHARS - 1].rstrip() + "…"


def deliver_message(text: str, *, token: str, chat_id: str, timeout: float = 20.0) -> str:
    """Отправляет текст в Telegram. Без токена или chat id печатает его в консоль.

    Возвращает ``telegram`` или ``console``.
    """
    if not token or not chat_id:
        print(text)
        return "console"
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return "telegram"
