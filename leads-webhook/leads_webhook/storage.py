from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from leads_webhook.models import Classification, LeadIn

HEADERS = [
    "ID",
    "Дата UTC",
    "Имя",
    "Телефон",
    "Email",
    "Сообщение",
    "Источник",
    "Категория",
    "Приоритет",
    "Кратко",
    "Классификатор",
]
SHEET_NAME = "Заявки"

_HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
_HEADER_FONT = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
_THIN = Border(
    left=Side(style="thin", color="D9E2F3"),
    right=Side(style="thin", color="D9E2F3"),
    top=Side(style="thin", color="D9E2F3"),
    bottom=Side(style="thin", color="D9E2F3"),
)
_COLUMN_CAPS = {"Сообщение": 48, "Кратко": 42, "Email": 32, "Имя": 24}


def lead_row(
    lead_id: str,
    created_at: str,
    lead: LeadIn,
    classification: Classification,
) -> list[str]:
    return [
        lead_id,
        created_at,
        lead.name,
        lead.phone or "",
        lead.email or "",
        lead.message,
        lead.source,
        classification.category,
        classification.priority,
        classification.summary,
        classification.source,
    ]


def _last_used_row(worksheet: Worksheet) -> int:
    # Не читаем worksheet["A1"] до записи: в openpyxl это создаёт пустую ячейку,
    # и следующий append уезжает на вторую строку.
    if not worksheet._cells:
        return 0
    return max(row for row, _column in worksheet._cells)


def _write_row(worksheet: Worksheet, row_index: int, values: list[str]) -> None:
    for column, value in enumerate(values, start=1):
        worksheet.cell(row_index, column, value or None)


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
        cap = _COLUMN_CAPS.get(str(header), 22)
        longest = len(str(header or ""))
        wrap = str(header) in {"Сообщение", "Кратко"}
        for (cell,) in worksheet.iter_rows(
            min_row=2,
            max_row=worksheet.max_row,
            min_col=col_idx,
            max_col=col_idx,
        ):
            if cell.value is not None:
                longest = max(longest, len(str(cell.value)))
            cell.alignment = Alignment(vertical="center", wrap_text=wrap)
        worksheet.column_dimensions[letter].width = min(max(longest + 2, 12), cap)


def append_lead_row(path: Path, row: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        workbook = load_workbook(path)
        if SHEET_NAME in workbook.sheetnames:
            worksheet = workbook[SHEET_NAME]
        else:
            worksheet = workbook.create_sheet(SHEET_NAME)
    else:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = SHEET_NAME
    last_row = _last_used_row(worksheet)
    header = worksheet._cells.get((1, 1))
    if header is None or header.value != HEADERS[0]:
        _write_row(worksheet, 1, HEADERS)
        last_row = max(last_row, 1)
    _write_row(worksheet, last_row + 1, row)
    _style_header(worksheet)
    _autosize(worksheet)
    workbook.save(path)
