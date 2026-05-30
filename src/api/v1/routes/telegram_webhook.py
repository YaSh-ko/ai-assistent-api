"""
Webhook Telegram Bot API (команда /start для бета-теста).
"""
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    """
    Принимает update от Telegram. Обрабатывает /start и сохраняет chat_id.
    """
    if settings.TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")

    try:
        update: dict[str, Any] = await request.json()
    except Exception as e:
        logger.warning("Telegram webhook invalid JSON: %s", e)
        return {"ok": True}

    try:
        await telegram_service.handle_webhook_update(db, update)
    except Exception as e:
        logger.error("Telegram webhook handler error: %s", e, exc_info=True)

    return {"ok": True}
