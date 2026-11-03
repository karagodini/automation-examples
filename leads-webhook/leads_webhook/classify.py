from __future__ import annotations

import json
import logging
import re

import requests
from pydantic import ValidationError

from leads_webhook.models import Category, Classification, LeadIn, Priority
from leads_webhook.settings import Settings

logger = logging.getLogger(__name__)

_CATEGORY_KEYWORDS: tuple[tuple[Category, tuple[str, ...]], ...] = (
    ("support", ("не работает", "ошибка", "баг", "support", "сломал", "почин")),
    (
        "pricing",
        (
            "цена",
            "цену",
            "цены",
            "цене",
            "стоимость",
            "прайс",
            "сколько стоит",
            "price",
            "бюджет",
            "budget",
        ),
    ),
    ("partnership", ("партн", "сотруднич", "partnership")),
    ("new_order", ("заказ", "купить", "оформить", "order")),
)
_URGENT = ("срочно", "urgent", "asap", "немедленно")

_SYSTEM_PROMPT = (
    "Ты классифицируешь входящие заявки бизнеса. "
    "Верни только JSON-объект с ключами "
    "category (new_order, pricing, support, partnership, other), "
    "priority (low, normal, high), "
    "summary (одна короткая фраза на языке заявки, до 160 символов). "
    "Без пояснений и без Markdown."
)


def _summary(message: str, limit: int = 160) -> str:
    text = " ".join(message.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def classify_by_rules(lead: LeadIn) -> Classification:
    text = f"{lead.name}\n{lead.message}".lower()
    category: Category = "other"
    for name, words in _CATEGORY_KEYWORDS:
        if any(word in text for word in words):
            category = name
            break
    urgent = any(word in text for word in _URGENT)
    if urgent or category == "support":
        priority: Priority = "high"
    elif category == "other":
        priority = "low"
    else:
        priority = "normal"
    return Classification(
        category=category,
        priority=priority,
        summary=_summary(lead.message),
        source="rules",
    )


def _chat_url(base: str) -> str:
    cleaned = base.strip().rstrip("/")
    suffix = "/chat/completions"
    if cleaned.endswith(suffix):
        return cleaned
    return cleaned + suffix


def _parse_llm_payload(content: str) -> Classification:
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("в ответе модели нет JSON")
    data = json.loads(text[start : end + 1])
    try:
        return Classification.model_validate(
            {
                "category": str(data["category"]).strip().lower(),
                "priority": str(data["priority"]).strip().lower(),
                "summary": _summary(str(data.get("summary") or "")),
                "source": "llm",
            }
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise ValueError("некорректный ответ модели") from exc


def classify_with_llm(lead: LeadIn, settings: Settings) -> Classification | None:
    headers = {"Content-Type": "application/json"}
    if settings.openai_api_key:
        headers["Authorization"] = f"Bearer {settings.openai_api_key}"
    payload = {
        "model": settings.openai_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Имя: {lead.name}\nИсточник: {lead.source}\nСообщение:\n{lead.message}"
                ),
            },
        ],
    }
    try:
        response = requests.post(
            _chat_url(settings.openai_api_base),
            headers=headers,
            json=payload,
            timeout=settings.request_timeout,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _parse_llm_payload(str(content))
    except (
        requests.RequestException,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        logger.warning("Классификация через LLM не удалась, используются правила: %s", exc)
        return None


def classify_lead(lead: LeadIn, settings: Settings) -> Classification:
    if settings.llm_enabled:
        classified = classify_with_llm(lead, settings)
        if classified is not None:
            return classified
    return classify_by_rules(lead)
