from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

import requests
from fastapi import FastAPI, Header, HTTPException

from leads_webhook.classify import classify_lead
from leads_webhook.models import LeadAccepted, LeadIn, NotifyChannel
from leads_webhook.notify import deliver_message, format_lead_message
from leads_webhook.settings import Settings
from leads_webhook.sheets import append_google_sheet
from leads_webhook.storage import append_lead_row, lead_row

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    current = settings or Settings.from_env()
    app = FastAPI(
        title="Leads webhook",
        version="1.0.0",
        summary="Принимает заявку с формы, пишет в таблицу и уведомляет менеджера.",
    )
    app.state.settings = current

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/leads", response_model=LeadAccepted)
    def create_lead(
        payload: LeadIn,
        x_webhook_secret: str | None = Header(default=None),
    ) -> LeadAccepted:
        if current.webhook_secret and x_webhook_secret != current.webhook_secret:
            raise HTTPException(status_code=401, detail="invalid webhook secret")

        classification = classify_lead(payload, current)
        lead_id = uuid4().hex[:12]
        created_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        row = lead_row(lead_id, created_at, payload, classification)
        append_lead_row(current.leads_xlsx_path, row)
        stored = ["excel"]
        if append_google_sheet(current, row):
            stored.append("google_sheets")

        message = format_lead_message(lead_id, payload, classification)
        notified: NotifyChannel
        try:
            notified = deliver_message(
                message,
                token=current.telegram_bot_token,
                chat_id=current.telegram_chat_id,
                timeout=current.request_timeout,
            )
        except requests.RequestException:
            logger.exception("Не удалось отправить заявку в Telegram")
            notified = "failed"

        return LeadAccepted(
            id=lead_id,
            name=payload.name,
            category=classification.category,
            priority=classification.priority,
            summary=classification.summary,
            classifier=classification.source,
            stored=stored,
            notified=notified,
        )

    return app


app = create_app()
