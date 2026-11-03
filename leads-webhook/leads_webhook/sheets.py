from __future__ import annotations

import logging

from leads_webhook.settings import Settings
from leads_webhook.storage import HEADERS

logger = logging.getLogger(__name__)


def append_google_sheet(settings: Settings, row: list[str]) -> bool:
    """Дописывает строку в Google Sheets. Если интеграция не настроена или упала — False."""
    if not settings.sheets_enabled:
        return False
    try:
        import gspread

        client = gspread.service_account(filename=settings.google_service_account_file)
        spreadsheet = client.open_by_key(settings.google_sheet_id)
        try:
            worksheet = spreadsheet.worksheet(settings.google_sheet_worksheet)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=settings.google_sheet_worksheet,
                rows=1000,
                cols=len(HEADERS),
            )
        existing = worksheet.get_all_values()
        if not existing:
            worksheet.append_row(HEADERS, value_input_option="RAW")
        worksheet.append_row(row, value_input_option="USER_ENTERED")
    except Exception:  # noqa: BLE001 — сбой Sheets не отменяет уже сохранённую заявку
        logger.exception("Не удалось записать заявку в Google Sheets")
        return False
    return True
