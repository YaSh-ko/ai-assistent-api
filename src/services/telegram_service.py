"""
Telegram Bot API — запись на бета-тест целиком в боте (email + chat_id).
"""
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_USERNAME_RE = re.compile(r"^@([a-zA-Z0-9_]{5,32})$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

BETA_WELCOME_MESSAGE = (
    "Привет! Это бот Impulse — запись на бета-тест.\n\n"
    "Отправьте ваш email одним сообщением — мы сохраним заявку и напишем, "
    "когда сервис выйдет в прод."
)

BETA_ALREADY_REGISTERED = (
    "Вы уже записаны на бета-тест Impulse.\n"
    "Когда сервис выйдет в прод — напишем вам здесь."
)

BETA_SIGNUP_CONFIRM_MESSAGE = (
    "Вы записаны на бета-тест Impulse!\n\n"
    "Email: {email}\n\n"
    "Когда сервис выйдет в прод, мы напишем вам здесь в Telegram.\n"
    "Спасибо, что с нами с самого начала."
)

BETA_INVALID_EMAIL = (
    "Не похоже на email. Отправьте адрес в формате name@example.com одним сообщением."
)

BETA_DUPLICATE_EMAIL = (
    "Этот email уже есть в списке бета-теста. Если это ошибка — напишите нам."
)

USER_HELP_MESSAGE = (
    "Impulse — бот записи на бета-тест.\n\n"
    "/start — записаться на бета-тест\n"
    "/help — эта справка"
)

ADMIN_HELP_MESSAGE = (
    "Команды администратора Impulse:\n\n"
    "/beta — последние заявки на бета-тест\n"
    "/myid — ваш chat_id для .env\n"
    "/help — справка"
)


def normalize_telegram_username(value: str) -> Optional[str]:
    """Return @username or None if invalid."""
    raw = value.strip()
    if not raw.startswith("@"):
        raw = f"@{raw}"
    if TELEGRAM_USERNAME_RE.match(raw):
        return raw.lower()
    return None


def telegram_username_key(value: str) -> Optional[str]:
    normalized = normalize_telegram_username(value)
    if not normalized:
        return None
    return normalized[1:]


def format_telegram_handle(username: Optional[str], chat_id: int) -> str:
    if username:
        return f"@{username.lower()}"
    return f"tg_user_{chat_id}"


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value.strip().lower()))


def _parse_command(text: str) -> str:
    if not text.startswith("/"):
        return ""
    token = text.split()[0]
    return token.split("@")[0].lower()


def _format_signup_row(telegram: str, email: str, created_at: Any, index: int) -> str:
    if isinstance(created_at, datetime):
        date_str = created_at.strftime("%d.%m.%Y %H:%M")
    else:
        date_str = str(created_at)[:16]
    return f"{index}. {telegram} · {email}\n   {date_str}"


class TelegramService:
    @property
    def enabled(self) -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN)

    def admin_chat_id(self) -> Optional[int]:
        raw = settings.TELEGRAM_ADMIN_CHAT_ID
        if raw is None:
            return None
        s = str(raw).strip()
        if "#" in s:
            s = s.split("#", 1)[0].strip()
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            logger.warning("Invalid TELEGRAM_ADMIN_CHAT_ID: %r", raw)
            return None

    def is_admin(self, chat_id: int) -> bool:
        admin_id = self.admin_chat_id()
        return admin_id is not None and chat_id == admin_id

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"

    async def send_message(self, chat_id: int, message: str) -> bool:
        if not self.enabled:
            logger.debug("Telegram bot token not configured, skip send_message")
            return False
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self._api_url("sendMessage"),
                    json={"chat_id": chat_id, "text": message},
                )
                if not resp.is_success:
                    logger.warning(
                        "Telegram sendMessage failed: status=%s body=%s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    return False
                return True
        except Exception as e:
            logger.warning("Telegram sendMessage error: %s", e)
            return False

    async def upsert_subscriber(
        self,
        db: AsyncSession,
        *,
        chat_id: int,
        username: Optional[str],
        awaiting_beta_email: bool = False,
    ) -> None:
        username_key = username.lower() if username else None
        if username_key:
            await db.execute(
                text(
                    """
                    DELETE FROM telegram_bot_subscribers
                    WHERE telegram_username = :username AND chat_id != :chat_id
                    """
                ),
                {"chat_id": chat_id, "username": username_key},
            )
        await db.execute(
            text(
                """
                INSERT INTO telegram_bot_subscribers (chat_id, telegram_username, awaiting_beta_email, updated_at)
                VALUES (:chat_id, :username, :awaiting, now())
                ON CONFLICT (chat_id) DO UPDATE SET
                    telegram_username = COALESCE(EXCLUDED.telegram_username, telegram_bot_subscribers.telegram_username),
                    awaiting_beta_email = EXCLUDED.awaiting_beta_email,
                    updated_at = now()
                """
            ),
            {"chat_id": chat_id, "username": username_key, "awaiting": awaiting_beta_email},
        )
        await db.commit()

    async def is_awaiting_beta_email(self, db: AsyncSession, chat_id: int) -> bool:
        result = await db.execute(
            text(
                """
                SELECT awaiting_beta_email FROM telegram_bot_subscribers
                WHERE chat_id = :chat_id
                LIMIT 1
                """
            ),
            {"chat_id": chat_id},
        )
        row = result.first()
        return bool(row[0]) if row else False

    async def is_already_registered(
        self,
        db: AsyncSession,
        telegram: str,
        email: Optional[str] = None,
    ) -> bool:
        if email:
            result = await db.execute(
                text(
                    """
                    SELECT 1 FROM beta_test
                    WHERE LOWER(telegram) = LOWER(:telegram) OR LOWER(email) = LOWER(:email)
                    LIMIT 1
                    """
                ),
                {"telegram": telegram, "email": email.strip().lower()},
            )
        else:
            result = await db.execute(
                text(
                    """
                    SELECT 1 FROM beta_test
                    WHERE LOWER(telegram) = LOWER(:telegram)
                    LIMIT 1
                    """
                ),
                {"telegram": telegram},
            )
        return result.first() is not None

    async def register_beta_signup(
        self,
        db: AsyncSession,
        *,
        chat_id: int,
        username: Optional[str],
        email: str,
    ) -> tuple[bool, str]:
        """Returns (success, user_message)."""
        telegram = format_telegram_handle(username, chat_id)
        email_norm = email.strip().lower()

        if await self.is_already_registered(db, telegram):
            await self.upsert_subscriber(db, chat_id=chat_id, username=username, awaiting_beta_email=False)
            return True, BETA_ALREADY_REGISTERED

        if await self.is_already_registered(db, telegram, email_norm):
            await self.upsert_subscriber(db, chat_id=chat_id, username=username, awaiting_beta_email=False)
            return False, BETA_DUPLICATE_EMAIL

        request_id = str(uuid.uuid4())
        await db.execute(
            text(
                """
                INSERT INTO beta_test (id, telegram, email)
                VALUES (:id, :telegram, :email)
                """
            ),
            {"id": request_id, "telegram": telegram, "email": email_norm},
        )
        await self.upsert_subscriber(db, chat_id=chat_id, username=username, awaiting_beta_email=False)
        await self.notify_admin_beta_signup(db, telegram, email_norm)
        logger.info("Beta signup via bot: telegram=%s email=%s", telegram, email_norm)
        return True, BETA_SIGNUP_CONFIRM_MESSAGE.format(email=email_norm)

    async def get_beta_signups_count(self, db: AsyncSession) -> int:
        result = await db.execute(text("SELECT COUNT(*) FROM beta_test"))
        row = result.first()
        return int(row[0]) if row else 0

    async def get_recent_beta_signups(self, db: AsyncSession, limit: int = 20) -> list[dict[str, Any]]:
        result = await db.execute(
            text(
                """
                SELECT telegram, email, created_at
                FROM beta_test
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        rows = result.fetchall()
        return [
            {"telegram": row[0], "email": row[1], "created_at": row[2]}
            for row in rows
        ]

    async def build_beta_list_message(self, db: AsyncSession) -> str:
        total = await self.get_beta_signups_count(db)
        if total == 0:
            return "Заявок на бета-тест пока нет."

        signups = await self.get_recent_beta_signups(db, limit=20)
        lines = [_format_signup_row(s["telegram"], s["email"], s["created_at"], i + 1) for i, s in enumerate(signups)]
        header = f"Заявки на бета-тест (всего: {total}, последние {len(signups)}):\n\n"
        return header + "\n\n".join(lines)

    async def notify_admin_beta_signup(self, db: AsyncSession, telegram: str, email: str) -> None:
        admin_id = self.admin_chat_id()
        if admin_id is None:
            return
        total = await self.get_beta_signups_count(db)
        message = (
            "Новая заявка на бета-тест Impulse\n\n"
            f"Telegram: {telegram}\n"
            f"Email: {email}\n\n"
            f"Всего заявок: {total}"
        )
        await self.send_message(admin_id, message)

    async def handle_start(self, db: AsyncSession, chat_id: int, username: Optional[str]) -> None:
        telegram = format_telegram_handle(username, chat_id)
        if await self.is_already_registered(db, telegram):
            await self.upsert_subscriber(db, chat_id=chat_id, username=username, awaiting_beta_email=False)
            await self.send_message(chat_id, BETA_ALREADY_REGISTERED)
            return
        await self.upsert_subscriber(db, chat_id=chat_id, username=username, awaiting_beta_email=True)
        await self.send_message(chat_id, BETA_WELCOME_MESSAGE)

    async def handle_email_message(
        self,
        db: AsyncSession,
        chat_id: int,
        username: Optional[str],
        text: str,
    ) -> None:
        if not await self.is_awaiting_beta_email(db, chat_id):
            await self.send_message(
                chat_id,
                "Чтобы записаться на бета-тест, отправьте /start",
            )
            return

        if not is_valid_email(text):
            await self.send_message(chat_id, BETA_INVALID_EMAIL)
            return

        success, message = await self.register_beta_signup(
            db,
            chat_id=chat_id,
            username=username,
            email=text,
        )
        await self.send_message(chat_id, message)

    async def handle_admin_beta_list(self, db: AsyncSession, chat_id: int) -> None:
        if not self.is_admin(chat_id):
            await self.send_message(chat_id, "Эта команда доступна только администратору.")
            return
        message = await self.build_beta_list_message(db)
        await self.send_message(chat_id, message)

    async def handle_help(self, chat_id: int) -> None:
        if self.is_admin(chat_id):
            await self.send_message(chat_id, ADMIN_HELP_MESSAGE)
        else:
            await self.send_message(chat_id, USER_HELP_MESSAGE)

    async def handle_myid(self, chat_id: int) -> None:
        admin_hint = ""
        if self.is_admin(chat_id):
            admin_hint = "\n\nВы настроены как администратор этого бота."
        await self.send_message(
            chat_id,
            f"Ваш chat_id: {chat_id}{admin_hint}\n\n"
            "Добавьте в .env API:\nTELEGRAM_ADMIN_CHAT_ID=" + str(chat_id),
        )

    async def handle_webhook_update(self, db: AsyncSession, update: dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None or not text:
            return

        chat_id = int(chat_id)
        from_user = message.get("from") or {}
        username = from_user.get("username") or chat.get("username")

        if text.startswith("/"):
            command = _parse_command(text)
            if command == "/start":
                await self.handle_start(db, chat_id, username)
            elif command in ("/beta", "/list"):
                await self.handle_admin_beta_list(db, chat_id)
            elif command == "/help":
                await self.handle_help(chat_id)
            elif command == "/myid":
                await self.handle_myid(chat_id)
            return

        await self.handle_email_message(db, chat_id, username, text)


telegram_service = TelegramService()
