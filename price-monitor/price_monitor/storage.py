from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from price_monitor.models import Product

HEADERS = ["Название", "Цена", "Валюта", "Наличие", "В наличии", "Рейтинг", "Ссылка"]

_HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
_HEADER_FONT = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
_THIN = Border(
    left=Side(style="thin", color="D9E2F3"),
    right=Side(style="thin", color="D9E2F3"),
    top=Side(style="thin", color="D9E2F3"),
    bottom=Side(style="thin", color="D9E2F3"),
)
_COLUMN_CAPS = {"Название": 42, "Наличие": 28, "Ссылка": 56}


def product_row(product: Product) -> list[object]:
    return [
        product.title,
        float(product.price),
        product.currency,
        product.availability,
        "да" if product.in_stock else "нет",
        product.rating,
        product.url,
    ]


def _style_header(worksheet: Worksheet) -> None:
    for cell in worksheet[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _THIN
    worksheet.row_dimensions[1].height = 22
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions


def _autosize(worksheet: Worksheet) -> None:
    headers = [cell.value for cell in worksheet[1]]
    for col_idx, header in enumerate(headers, start=1):
        letter = get_column_letter(col_idx)
        cap = _COLUMN_CAPS.get(str(header), 18)
        longest = len(str(header or ""))
        for (cell,) in worksheet.iter_rows(
            min_row=2,
            max_row=worksheet.max_row,
            min_col=col_idx,
            max_col=col_idx,
        ):
            if cell.value is not None:
                longest = max(longest, len(str(cell.value)))
            if header == "Цена" and isinstance(cell.value, (int, float)):
                cell.number_format = "#,##0.00"
            if header == "Рейтинг" and isinstance(cell.value, int):
                cell.number_format = "0"
            cell.alignment = Alignment(
                vertical="center",
                wrap_text=header in {"Название", "Ссылка"},
            )
        worksheet.column_dimensions[letter].width = min(max(longest + 2, 12), cap)


def save_excel(path: Path, products: list[Product]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Каталог"
    worksheet.append(HEADERS)
    for product in products:
        worksheet.append(product_row(product))
    _style_header(worksheet)
    _autosize(worksheet)
    workbook.save(path)


def save_csv(path: Path, products: list[Product]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        for product in products:
            row = product_row(product)
            row[1] = f"{product.price:.2f}"
            writer.writerow(row)


def save_snapshot(path: Path, products: list[Product], *, source_url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_url": source_url,
        "products": [item.to_dict() for item in products],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_snapshot(path: Path) -> tuple[list[Product], str] | None:
    """Возвращает (товары, source_url) или None, если снимка ещё нет."""
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    products = [Product.from_dict(item) for item in payload.get("products", [])]
    return products, str(payload.get("source_url") or "")


def read_excel_headers(path: Path) -> list[str]:
    workbook = load_workbook(path)
    worksheet = workbook.active
    return [str(cell.value) for cell in worksheet[1]]
