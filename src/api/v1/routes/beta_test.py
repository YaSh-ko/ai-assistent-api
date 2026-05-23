"""
Публичный эндпоинт заявки на бета-тестирование (форма на delez.tech/beta-test).
"""
import logging
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.core.database import get_db
from src.api.v1.schemas.beta_test import BetaTestSignupRequest, BetaTestSignupResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Заявка на бета-тестирование",
    description="Сохраняет telegram и email в таблицу beta_test.",
)
async def submit_beta_signup(
    body: BetaTestSignupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BetaTestSignupResponse:
    request_id = str(uuid.uuid4())
    await db.execute(
        text(
            """
            INSERT INTO beta_test (id, telegram, email)
            VALUES (:id, :telegram, :email)
            """
        ),
        {
            "id": request_id,
            "telegram": body.telegram.strip(),
            "email": str(body.email).strip().lower(),
        },
    )
    await db.commit()
    logger.info("Beta test signup recorded: email=%s", str(body.email).strip().lower())
    return BetaTestSignupResponse(success=True, id=request_id)
