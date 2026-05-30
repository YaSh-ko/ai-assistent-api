"""Схемы заявки на бета-тестирование."""
from pydantic import BaseModel, EmailStr, Field


class BetaTestSignupRequest(BaseModel):
    """Тело запроса (legacy API; запись через Telegram-бот предпочтительнее)."""

    telegram: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Telegram (@username или ссылка)",
    )
    email: EmailStr = Field(..., description="Email для связи")


class BetaTestSignupResponse(BaseModel):
    """Ответ после успешной записи заявки."""

    success: bool = True
    id: str
    telegram_notified: bool = False
