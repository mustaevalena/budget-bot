import base64
import json
import re
from datetime import datetime

import anthropic

from config import ANTHROPIC_API_KEY, CATEGORIES

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = f"""Ты парсишь данные о расходах из скринов банковских приложений (Raiffeisen RU, Freedom Bank KZ)
или текстовых описаний на русском языке. Транзакции совершаются в Сербии, валюта — RSD (динары).

Всегда возвращай ТОЛЬКО валидный JSON без markdown-блоков:
{{
  "date": "DD.MM",
  "merchant": "название магазина или получателя",
  "amount": 1234,
  "suggested_category": "одна категория из списка"
}}

Правила:
- date: формат DD.MM, если дата не указана — используй сегодняшнюю
- merchant: короткое название (без лишних суффиксов типа SRB, doo, d.o.o.)
- amount: целое число в RSD. Если валюта другая — всё равно запиши как есть
- suggested_category: строго одна из списка ниже

Список категорий:
{chr(10).join(f'- {c}' for c in CATEGORIES)}
"""


def _today_ddmm() -> str:
    return datetime.now().strftime("%d.%m")


def _parse_response(text: str) -> dict:
    text = text.strip()
    # strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not data.get("date"):
        data["date"] = _today_ddmm()
    if data.get("suggested_category") not in CATEGORIES:
        data["suggested_category"] = CATEGORIES[0]
    data["amount"] = int(data.get("amount", 0))
    return data


def parse_screenshot(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    b64 = base64.standard_b64encode(image_bytes).decode()
    today = _today_ddmm()
    response = _client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime_type, "data": b64},
                    },
                    {
                        "type": "text",
                        "text": f"Сегодня {today}. Распознай транзакцию на скрине и верни JSON.",
                    },
                ],
            }
        ],
    )
    return _parse_response(response.content[0].text)


def parse_text(text: str) -> dict:
    today = _today_ddmm()
    response = _client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Сегодня {today}. Разбери описание расхода и верни JSON:\n{text}",
            }
        ],
    )
    return _parse_response(response.content[0].text)
