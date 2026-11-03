from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from leads_webhook.main import create_app
from leads_webhook.settings import Settings
from leads_webhook.storage import HEADERS


def _client(tmp_path: Path, **overrides: object) -> TestClient:
    settings = Settings(leads_xlsx_path=tmp_path / "leads.xlsx", **overrides)  # type: ignore[arg-type]
    return TestClient(create_app(settings))


def test_health_and_lead_land_in_excel_and_console(tmp_path: Path, capsys) -> None:
    client = _client(tmp_path)
    assert client.get("/health").json() == {"status": "ok"}
    response = client.post(
        "/leads",
        json={
            "name": "Анна",
            "phone": "+7 999 123-45-67",
            "message": "Сколько стоит связать заявки с Google Таблицей?",
            "source": "site",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "pricing"
    assert body["priority"] == "normal"
    assert body["classifier"] == "rules"
    assert body["stored"] == ["excel"]
    assert body["notified"] == "console"
    assert "Сколько стоит" in body["summary"]
    printed = capsys.readouterr().out
    assert body["id"] in printed
    assert "Категория: pricing" in printed

    workbook = load_workbook(tmp_path / "leads.xlsx")
    sheet = workbook["Заявки"]
    assert [cell.value for cell in sheet[1]] == HEADERS
    assert sheet.freeze_panes == "A2"
    assert sheet["A1"].font.bold is True
    assert sheet.column_dimensions["F"].width >= 12
    assert sheet["A2"].value == body["id"]
    assert sheet["C2"].value == "Анна"
    assert sheet["H2"].value == "pricing"
    assert sheet["K2"].value == "rules"

    again = client.post(
        "/leads",
        json={
            "name": "Иван",
            "email": "ivan@example.com",
            "message": "Не работает форма на главной",
        },
    )
    assert again.status_code == 200
    assert again.json()["category"] == "support"
    workbook = load_workbook(tmp_path / "leads.xlsx")
    assert workbook["Заявки"].max_row == 3


def test_validation_error_and_webhook_secret(tmp_path: Path) -> None:
    open_client = _client(tmp_path)
    rejected = open_client.post("/leads", json={"name": "Анна", "message": "Без контакта совсем"})
    assert rejected.status_code == 422

    secret_client = _client(tmp_path, webhook_secret="s3cret")
    denied = secret_client.post(
        "/leads",
        json={"name": "Анна", "phone": "+79991234567", "message": "Нужна консультация"},
    )
    assert denied.status_code == 401
    allowed = secret_client.post(
        "/leads",
        headers={"X-Webhook-Secret": "s3cret"},
        json={"name": "Анна", "phone": "+79991234567", "message": "Нужна консультация"},
    )
    assert allowed.status_code == 200


def test_sheets_flag_and_telegram_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("leads_webhook.main.append_google_sheet", lambda settings, row: True)

    def boom(*args, **kwargs):
        raise __import__("requests").ConnectionError("telegram down")

    monkeypatch.setattr("leads_webhook.main.deliver_message", boom)
    client = _client(tmp_path, telegram_bot_token="token", telegram_chat_id="1")
    response = client.post(
        "/leads",
        json={"name": "Анна", "email": "anna@example.com", "message": "Хочу заказать отчёт"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stored"] == ["excel", "google_sheets"]
    assert body["notified"] == "failed"
    assert body["category"] == "new_order"
    assert (tmp_path / "leads.xlsx").exists()
