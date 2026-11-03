from __future__ import annotations

import requests

from leads_webhook.classify import classify_by_rules, classify_lead
from leads_webhook.models import LeadIn
from leads_webhook.notify import format_lead_message
from leads_webhook.settings import Settings


def _lead(message: str, name: str = "Анна") -> LeadIn:
    return LeadIn(name=name, phone="+7 999 123-45-67", message=message, source="site")


def test_rules_cover_pricing_support_order_partnership_and_other() -> None:
    pricing = classify_by_rules(_lead("Сколько стоит связать заявки с Google Таблицей?"))
    assert pricing.category == "pricing"
    assert pricing.priority == "normal"
    assert pricing.source == "rules"

    urgent_price = classify_by_rules(_lead("Срочно напишите цену доработки"))
    assert urgent_price.category == "pricing"
    assert urgent_price.priority == "high"

    support = classify_by_rules(_lead("Не работает оплата на сайте"))
    assert support.category == "support"
    assert support.priority == "high"

    order = classify_by_rules(_lead("Хочу заказать бота для заявок"))
    assert order.category == "new_order"
    assert order.priority == "normal"

    partner = classify_by_rules(_lead("Давайте обсудим сотрудничество"))
    assert partner.category == "partnership"
    assert partner.priority == "normal"

    other = classify_by_rules(_lead("Интересует, как вы работаете"))
    assert other.category == "other"
    assert other.priority == "low"


def test_llm_result_is_used_when_configured(monkeypatch) -> None:
    settings = Settings(
        openai_api_base="https://example.test/v1",
        openai_api_key="test-key",
        openai_model="demo-model",
    )
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '```json\n{"category":"partnership","priority":"low",'
                                '"summary":"Предлагает совместный вебинар"}\n```'
                            )
                        }
                    }
                ]
            }

    def fake_post(url: str, **kwargs: object) -> _Response:
        captured["url"] = url
        captured["json"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        return _Response()

    monkeypatch.setattr("leads_webhook.classify.requests.post", fake_post)
    result = classify_lead(_lead("Можем сделать совместный вебинар"), settings)
    assert result.source == "llm"
    assert result.category == "partnership"
    assert result.priority == "low"
    assert result.summary == "Предлагает совместный вебинар"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    body = captured["json"]
    assert isinstance(body, dict)
    user_text = body["messages"][1]["content"]
    assert "Можем сделать совместный вебинар" in user_text
    assert "+7" not in user_text
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer test-key"


def test_llm_failure_falls_back_to_rules(monkeypatch) -> None:
    settings = Settings(openai_api_base="http://127.0.0.1:11434/v1", openai_model="llama")

    def boom(*args: object, **kwargs: object) -> None:
        raise requests.Timeout("slow")

    monkeypatch.setattr("leads_webhook.classify.requests.post", boom)
    result = classify_lead(_lead("Сколько стоит подключить CRM?"), settings)
    assert result.source == "rules"
    assert result.category == "pricing"
    assert result.priority == "normal"


def test_invalid_llm_json_falls_back_to_rules(monkeypatch) -> None:
    settings = Settings(openai_api_base="https://openrouter.ai/api/v1", openai_model="demo")

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "не json"}}]}

    monkeypatch.setattr("leads_webhook.classify.requests.post", lambda *a, **k: _Response())
    result = classify_lead(_lead("Хочу купить сопровождение"), settings)
    assert result.source == "rules"
    assert result.category == "new_order"


def test_lead_telegram_text() -> None:
    lead = _lead("Сколько стоит связать заявки с Google Таблицей?")
    classification = classify_by_rules(lead)
    text = format_lead_message("ab12cd34ef56", lead, classification)
    assert text == (
        "Новая заявка ab12cd34ef56\n"
        "Имя: Анна\n"
        "Телефон: +7 999 123-45-67\n"
        "Email: —\n"
        "Источник: site\n"
        "Категория: pricing\n"
        "Приоритет: normal\n"
        "Классификатор: rules\n"
        "\n"
        "Сколько стоит связать заявки с Google Таблицей?"
    )
