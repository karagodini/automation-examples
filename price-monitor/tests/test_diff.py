from __future__ import annotations

from decimal import Decimal

from price_monitor.diff import diff_products
from price_monitor.models import Product
from price_monitor.notify import format_diff_message
from price_monitor.storage import load_snapshot, save_snapshot


def _product(
    title: str,
    price: str,
    url: str,
    *,
    rating: int = 3,
    in_stock: bool = True,
) -> Product:
    return Product(
        title=title,
        price=Decimal(price),
        currency="GBP",
        availability="In stock" if in_stock else "Out of stock",
        in_stock=in_stock,
        rating=rating,
        url=url,
    )


def test_diff_detects_new_product_and_price_change() -> None:
    attic = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    velvet = "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html"
    sharp = "https://books.toscrape.com/catalogue/sharp-objects_997/index.html"
    previous = [
        _product("A Light in the Attic", "51.77", attic),
        _product("Tipping the Velvet", "53.74", velvet, rating=1),
    ]
    current = [
        _product("A Light in the Attic", "51.77", attic, rating=5),
        _product("Tipping the Velvet", "49.00", velvet, rating=1),
        _product("Sharp Objects", "47.82", sharp, rating=4),
    ]
    diff = diff_products(previous, current)
    assert diff.has_alerts is True
    assert [item.title for item in diff.new_products] == ["Sharp Objects"]
    assert len(diff.price_changes) == 1
    change = diff.price_changes[0]
    assert change.product.title == "Tipping the Velvet"
    assert change.old_price == Decimal("53.74")
    assert change.new_price == Decimal("49.00")
    assert change.delta == Decimal("-4.74")
    assert diff.removed_count == 0


def test_diff_ignores_rating_only_change_and_counts_removed() -> None:
    attic = "https://books.example/attic"
    gone = "https://books.example/gone"
    previous = [
        _product("Attic", "10.00", attic, rating=1),
        _product("Gone", "8.00", gone),
    ]
    current = [_product("Attic", "10.00", attic, rating=5)]
    diff = diff_products(previous, current)
    assert diff.has_alerts is False
    assert diff.new_products == []
    assert diff.price_changes == []
    assert diff.removed_count == 1


def test_snapshot_roundtrip(tmp_path) -> None:
    path = tmp_path / "snapshot.json"
    products = [_product("Soumission", "50.10", "https://books.example/soumission", in_stock=False)]
    save_snapshot(path, products, source_url="https://books.toscrape.com/catalogue/page-1.html")
    loaded, source = load_snapshot(path)
    assert source == "https://books.toscrape.com/catalogue/page-1.html"
    assert loaded == products
    assert load_snapshot(tmp_path / "missing.json") is None


def test_telegram_message_lists_new_items_and_price_delta() -> None:
    attic = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    velvet = "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html"
    previous = [_product("Tipping the Velvet", "53.74", velvet, rating=1)]
    current = [
        _product("Tipping the Velvet", "49.00", velvet, rating=1),
        _product("A Light in the Attic", "51.77", attic, in_stock=True, rating=3),
    ]
    diff = diff_products(previous, current)
    text = format_diff_message(
        diff,
        source_url="https://books.toscrape.com/catalogue/page-1.html",
        checked=2,
    )
    assert text == (
        "Мониторинг цен — books.toscrape.com\n"
        "Источник: https://books.toscrape.com/catalogue/page-1.html\n"
        "Проверено позиций: 2\n"
        "Новых товаров: 1\n"
        "Изменения цен: 1\n"
        "\n"
        "Новые товары:\n"
        "• A Light in the Attic — 51.77 GBP, в наличии, рейтинг 3/5\n"
        f"  {attic}\n"
        "\n"
        "Изменения цен:\n"
        "• Tipping the Velvet — 53.74 → 49.00 GBP (-8.8%)\n"
        f"  {velvet}"
    )
