from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from price_monitor.main import MonitorConfig, run
from price_monitor.models import Product
from price_monitor.storage import HEADERS, load_snapshot, save_snapshot


def _product(title: str, price: str, url: str) -> Product:
    return Product(
        title=title,
        price=Decimal(price),
        currency="GBP",
        availability="In stock",
        in_stock=True,
        rating=3,
        url=url,
    )


class _Response:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _OnePage:
    def __init__(self, html: str) -> None:
        self.html = html

    def get(self, url: str, timeout: float = 20) -> _Response:
        return _Response(self.html)

    def close(self) -> None:
        return None


def _config(tmp_path: Path, **kwargs: object) -> MonitorConfig:
    defaults: dict[str, object] = {
        "start_url": "https://books.toscrape.com/catalogue/page-1.html",
        "max_pages": 1,
        "data_dir": tmp_path,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "delay_seconds": 0,
    }
    defaults.update(kwargs)
    return MonitorConfig(**defaults)  # type: ignore[arg-type]


HTML = """
<article class="product_pod">
  <p class="star-rating Three"></p>
  <h3>
    <a href="a-light-in-the-attic_1000/index.html" title="A Light in the Attic">A Light...</a>
  </h3>
  <div class="product_price">
    <p class="price_color">£51.77</p>
    <p class="instock availability">In stock</p>
  </div>
</article>
"""


def test_first_run_writes_excel_and_skips_alert(tmp_path: Path, capsys) -> None:
    code = run(_config(tmp_path), session=_OnePage(HTML))
    assert code == 0
    assert capsys.readouterr().out == ""

    workbook = load_workbook(tmp_path / "catalogue.xlsx")
    sheet = workbook.active
    assert sheet.title == "Каталог"
    assert [cell.value for cell in sheet[1]] == HEADERS
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref is not None
    assert sheet["A1"].font.bold is True
    assert str(sheet["A1"].font.color.rgb).endswith("FFFFFF")
    assert sheet.column_dimensions["A"].width >= 12
    assert sheet["A2"].value == "A Light in the Attic"
    assert sheet["B2"].value == pytest.approx(51.77)
    assert sheet["B2"].number_format == "#,##0.00"
    assert sheet["E2"].value == "да"
    assert sheet["F2"].value == 3

    csv_text = (tmp_path / "catalogue.csv").read_text(encoding="utf-8-sig")
    assert "Название,Цена" in csv_text
    assert "A Light in the Attic,51.77,GBP,In stock,да,3," in csv_text
    loaded, _source = load_snapshot(tmp_path / "snapshot.json")
    assert loaded is not None
    assert loaded[0].title == "A Light in the Attic"


def test_second_run_prints_summary_when_telegram_is_not_configured(tmp_path: Path, capsys) -> None:
    url = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    save_snapshot(
        tmp_path / "snapshot.json",
        [_product("A Light in the Attic", "40.00", url)],
        source_url="https://books.toscrape.com/catalogue/page-1.html",
    )
    code = run(_config(tmp_path), session=_OnePage(HTML))
    assert code == 0
    printed = capsys.readouterr().out
    assert "Изменения цен: 1" in printed
    assert "40.00 → 51.77 GBP" in printed
    loaded, _source = load_snapshot(tmp_path / "snapshot.json")
    assert loaded is not None
    assert loaded[0].price == Decimal("51.77")


def test_failed_telegram_keeps_previous_snapshot(tmp_path: Path, monkeypatch) -> None:
    url = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    save_snapshot(
        tmp_path / "snapshot.json",
        [_product("A Light in the Attic", "40.00", url)],
        source_url="https://books.toscrape.com/catalogue/page-1.html",
    )

    def boom(*args, **kwargs):
        raise __import__("requests").ConnectionError("bot down")

    monkeypatch.setattr("price_monitor.main.deliver_message", boom)
    code = run(
        _config(tmp_path, telegram_bot_token="token", telegram_chat_id="1"),
        session=_OnePage(HTML),
    )
    assert code == 1
    loaded, _source = load_snapshot(tmp_path / "snapshot.json")
    assert loaded is not None
    assert loaded[0].price == Decimal("40.00")
    assert (tmp_path / "catalogue.xlsx").exists()
