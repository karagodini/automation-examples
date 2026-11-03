from __future__ import annotations

from typing import Literal

import requests

from leads_webhook.models import Classification, LeadIn


def format_lead_message(lead_id: str, lead: LeadIn, classification: Classification) -> str:
    return "\n".join(
        [
            f"Новая заявка {lead_id}",
            f"Имя: {lead.name}",
            f"Телефон: {lead.phone or '—'}",
            f"Email: {lead.email or '—'}",
            f"Источник: {lead.source}",
            f"Категория: {classification.category}",
            f"Приоритет: {classification.priority}",
            f"Классификатор: {classification.source}",
            "",
            classification.summary,
        ]
    )


def deliver_message(
    text: str,
    *,
    token: str,
    chat_id: str,
    timeout: float = 20.0,
) -> Literal["telegram", "console"]:
    """Отправляет текст в Telegram. Без токена или chat id печатает его в консоль."""
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
