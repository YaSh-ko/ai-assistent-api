"""
Insights endpoints for deep analytics.
"""
import logging
from datetime import date, timedelta
from typing import Annotated, List, Optional

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user_id
from src.core.config import settings
from src.core.database import get_db
from src.data.repositories.entry import EntryRepository
from src.api.v1.schemas.insights import EntryInsightsResponse, EntryPatternItem

logger = logging.getLogger(__name__)

router = APIRouter()


class SummarizeEntityItem(BaseModel):
    id: str
    type: str
    title: str
    description: str = ""
    status: str = ""
    created_at: str = ""


class SummarizeRequest(BaseModel):
    entities: List[SummarizeEntityItem]
    context: str
    date: Optional[str] = None


class SummarizeResponse(BaseModel):
    summary: str


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_entities(
    request: SummarizeRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Proxy to AI service for LLM-powered summaries."""
    url = f"{settings.AI_SERVICE_URL}/api/v1/ai/summarize"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=request.model_dump())
            resp.raise_for_status()
            return SummarizeResponse(**resp.json())
    except Exception as e:
        logger.warning("[Insights] AI summarize failed: %s", e)
        return SummarizeResponse(summary="Не удалось сгенерировать сводку. Попробуйте позже.")


def _period_start(period: str, today: date) -> date:
    if period == "day":
        return today
    if period == "week":
        return today - timedelta(days=6)
    if period == "month":
        return today - timedelta(days=29)
    if period == "year":
        return today - timedelta(days=364)
    return date(1970, 1, 1)


@router.get("/entries", response_model=EntryInsightsResponse)
async def get_entries_insights(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: Annotated[str, Query(description="day, week, month, year, all")] = "month",
):
    """
    Deep entry analytics by period.
    """
    repo = EntryRepository(db)
    all_entries = await repo.get_by_user_id(user_id, skip=0, limit=5000)

    today = date.today()
    since = _period_start(period, today)

    filtered = [e for e in all_entries if e.event_date >= since]
    total_entries = len(filtered)
    active_days = len({e.event_date.isoformat() for e in filtered})
    avg_per_active = round(total_entries / active_days, 2) if active_days > 0 else 0.0
    avg_len = round(sum(len(e.description or "") for e in filtered) / total_entries, 2) if total_entries > 0 else 0.0

    strongest = max(filtered, key=lambda e: len(e.description or ""), default=None)
    strongest_title = strongest.title if strongest and strongest.title else (strongest.description[:80] if strongest else "")
    strongest_len = len(strongest.description or "") if strongest else 0

    weekday_map: dict[str, int] = {}
    hour_map: dict[str, int] = {}
    for entry in filtered:
        weekday_label = entry.event_date.strftime("%A")
        weekday_map[weekday_label] = weekday_map.get(weekday_label, 0) + 1
        hour_label = str(entry.created_at.hour)
        hour_map[hour_label] = hour_map.get(hour_label, 0) + 1

    repeating_patterns = [
        EntryPatternItem(label=label, count=count)
        for label, count in sorted(weekday_map.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    growth_triggers = [
        EntryPatternItem(label=f"Активный час: {label}:00", count=count)
        for label, count in sorted(hour_map.items(), key=lambda x: x[1], reverse=True)[:3]
    ]
    burnout_triggers = [
        EntryPatternItem(label=f"Нагрузка в {label}", count=count)
        for label, count in sorted(weekday_map.items(), key=lambda x: x[1], reverse=True)[-2:]
    ] if weekday_map else []

    return EntryInsightsResponse(
        period=period,
        total_entries=total_entries,
        active_days=active_days,
        average_entries_per_active_day=avg_per_active,
        average_text_length=avg_len,
        strongest_entry_title=strongest_title,
        strongest_entry_length=strongest_len,
        growth_triggers=growth_triggers,
        burnout_triggers=burnout_triggers,
        repeating_patterns=repeating_patterns,
    )
