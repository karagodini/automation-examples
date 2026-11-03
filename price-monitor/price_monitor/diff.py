from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from price_monitor.models import Product


@dataclass(frozen=True)
class PriceChange:
    product: Product
    old_price: Decimal
    new_price: Decimal

    @property
    def delta(self) -> Decimal:
        return self.new_price - self.old_price


@dataclass(frozen=True)
class CatalogueDiff:
    new_products: list[Product]
    price_changes: list[PriceChange]
    removed_count: int = 0

    @property
    def has_alerts(self) -> bool:
        return bool(self.new_products or self.price_changes)


def diff_products(previous: list[Product], current: list[Product]) -> CatalogueDiff:
    """Новые URL и позиции, у которых изменилась цена. Рейтинг сам по себе не шлёт алерт."""
    previous_by_url = {item.url: item for item in previous}
    current_urls = {item.url for item in current}
    new_products = [item for item in current if item.url not in previous_by_url]
    changes: list[PriceChange] = []
    for item in current:
        old = previous_by_url.get(item.url)
        if old is None or old.price == item.price:
            continue
        changes.append(PriceChange(product=item, old_price=old.price, new_price=item.price))
    removed = sum(1 for url in previous_by_url if url not in current_urls)
    return CatalogueDiff(
        new_products=new_products,
        price_changes=changes,
        removed_count=removed,
    )
