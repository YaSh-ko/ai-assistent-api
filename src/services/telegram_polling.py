"""
Long polling для Telegram Bot API — локальная разработка без публичного webhook.
"""
import asyncio
import logging
from typing import Any

import httpx

from src.core.config import settings
from src.core.database import async_session_maker
from src.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)


async def _fetch_updates(offset: int) -> list[dict[str, Any]]:
    if not telegram_service.enabled:
        return []
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 25, "offset": offset, "allowed_updates": '["message","edited_message"]'}
    async with httpx.AsyncClient(timeout=35) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    if not data.get("ok"):
        logger.warning("Telegram getUpdates failed: %s", data)
        return []
    return data.get("result") or []


async def telegram_polling_loop(stop_event: asyncio.Event) -> None:
    """Poll Telegram getUpdates and process messages like webhook."""
    logger.info("Telegram long polling started (TELEGRAM_USE_POLLING=true)")
    offset = 0
    while not stop_event.is_set():
        try:
            updates = await _fetch_updates(offset)
            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                async with async_session_maker() as db:
                    try:
                        await telegram_service.handle_webhook_update(db, update)
                    except Exception as e:
                        logger.error("Telegram polling handler error: %s", e, exc_info=True)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Telegram polling error: %s", e)
            await asyncio.sleep(3)
    logger.info("Telegram long polling stopped")
