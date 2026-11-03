from __future__ import annotations

import pytest
from pydantic import ValidationError

from leads_webhook.models import LeadIn


def test_lead_accepts_phone_or_email() -> None:
    by_phone = LeadIn(name="Анна", phone="+7 (999) 123-45-67", message="Нужен расчёт интеграции")
    assert by_phone.phone == "+7 (999) 123-45-67"
    assert by_phone.source == "website"
    by_email = LeadIn(
        name="Иван",
        email="ivan@example.com",
        phone="  ",
        message="Хочу обсудить задачу",
        source=" landing ",
    )
    assert by_email.email == "ivan@example.com"
    assert by_email.phone is None
    assert by_email.source == "landing"


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        (
            {"name": "А", "phone": "+79991234567", "message": "Достаточно длинное"},
            "string_too_short",
        ),
        ({"name": "Анна", "message": "Достаточно длинное"}, "нужен телефон или email"),
        ({"name": "Анна", "phone": "123", "message": "Достаточно длинное"}, "10 до 15"),
        (
            {"name": "Анна", "email": "not-an-email", "message": "Достаточно длинное"},
            "некорректный email",
        ),
        ({"name": "Анна", "phone": "+79991234567", "message": "   ок"}, "string_too_short"),
    ],
)
def test_lead_rejects_bad_payload(payload: dict[str, str], fragment: str) -> None:
    with pytest.raises(ValidationError) as caught:
        LeadIn.model_validate(payload)
    assert fragment in str(caught.value)
