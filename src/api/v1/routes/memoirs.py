"""
Memoirs endpoints (public/private/recommendations).
"""
from datetime import date, timedelta
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user_id
from src.core.database import get_db
from src.data.repositories.entry import EntryRepository
from src.infrastructure.neo4j_client import neo4j_client
from src.api.v1.schemas.memoirs import (
    PublicMemoirCreateRequest,
    PublicMemoirCreateResponse,
    PublicMemoirsFeedResponse,
    PublicMemoirItem,
    MemoirRecommendationsResponse,
    MemoirRecommendationItem,
    PrivateStoryResponse,
)

router = APIRouter()


def _since_date(period: str) -> date:
    today = date.today()
    if period == "month":
        return today - timedelta(days=29)
    if period == "year":
        return today - timedelta(days=364)
    return date(1970, 1, 1)


@router.get("/public", response_model=PublicMemoirsFeedResponse)
async def get_public_memoirs_feed():
    """Get public memoir feed."""
    query = """
    MATCH (m:PublicMemoir)
    RETURN m
    ORDER BY m.created_at DESC
    LIMIT 100
    """
    result = await neo4j_client.execute_query_async(query, {})
    items: list[PublicMemoirItem] = []
    for row in result:
        node = dict(row["m"])
        items.append(
            PublicMemoirItem(
                id=str(node.get("id", "")),
                title=node.get("title", ""),
                content=node.get("content", ""),
                author_id=node.get("author_id", ""),
                created_at=str(node.get("created_at", "")),
                likes=int(node.get("likes", 0)),
            )
        )
    return PublicMemoirsFeedResponse(items=items)


@router.post("/public", response_model=PublicMemoirCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_public_memoir(
    request: PublicMemoirCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Create a public memoir post."""
    memoir_id = str(uuid4())
    query = """
    CREATE (m:PublicMemoir {
      id: $id,
      title: $title,
      content: $content,
      author_id: $author_id,
      likes: 0,
      created_at: datetime()
    })
    RETURN m
    """
    try:
        result = await neo4j_client.execute_query_async(
            query,
            {
                "id": memoir_id,
                "title": request.title,
                "content": request.content,
                "author_id": user_id,
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create memoir: {str(e)}",
        )

    node = dict(result[0]["m"])
    return PublicMemoirCreateResponse(
        id=str(node.get("id", memoir_id)),
        title=node.get("title", request.title),
        content=node.get("content", request.content),
        author_id=node.get("author_id", user_id),
        created_at=str(node.get("created_at", "")),
        likes=int(node.get("likes", 0)),
    )


@router.post("/public/{memoir_id}/like", response_model=PublicMemoirItem)
async def like_public_memoir(memoir_id: str):
    """Increment likes of public memoir."""
    query = """
    MATCH (m:PublicMemoir {id: $memoir_id})
    SET m.likes = coalesce(m.likes, 0) + 1,
        m.updated_at = datetime()
    RETURN m
    """
    result = await neo4j_client.execute_query_async(query, {"memoir_id": memoir_id})
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memoir not found")
    node = dict(result[0]["m"])
    return PublicMemoirItem(
        id=str(node.get("id", memoir_id)),
        title=node.get("title", ""),
        content=node.get("content", ""),
        author_id=node.get("author_id", ""),
        created_at=str(node.get("created_at", "")),
        likes=int(node.get("likes", 0)),
    )


@router.get("/private/story", response_model=PrivateStoryResponse)
async def get_private_story(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: Annotated[str, Query(description="month, year, all")] = "all",
):
    """Build private memoir story from entries/goals/experiments."""
    repo = EntryRepository(db)
    entries = await repo.get_by_user_id(user_id, skip=0, limit=2000)
    filtered = [e for e in entries if e.event_date >= _since_date(period)]

    goal_query = """
    MATCH (g:Goal {user_id: $user_id})
    RETURN g.status as status, count(g) as count
    """
    exp_query = """
    MATCH (e:Experiment {user_id: $user_id})
    RETURN e.status as status, count(e) as count
    """
    goals_rows = await neo4j_client.execute_query_async(goal_query, {"user_id": user_id})
    exp_rows = await neo4j_client.execute_query_async(exp_query, {"user_id": user_id})

    total_entries = len(filtered)
    completed_goals = sum(int(r.get("count", 0)) for r in goals_rows if str(r.get("status", "")).lower() == "completed")
    active_experiments = sum(int(r.get("count", 0)) for r in exp_rows if str(r.get("status", "")).lower() == "active")
    timeline_points = [
        f"{e.event_date.isoformat()}: {(e.title or e.description[:80]).strip()}"
        for e in sorted(filtered, key=lambda x: x.event_date)[:12]
    ]

    narrative = (
        f"За период '{period}' ты зафиксировал(а) {total_entries} событий. "
        f"Завершённых целей: {completed_goals}. "
        f"Активных экспериментов: {active_experiments}. "
        "Главная динамика — переход от наблюдения к осознанным изменениям через цели и эксперименты."
    )
    return PrivateStoryResponse(
        title="Хронология моего пути",
        narrative=narrative,
        timeline_points=timeline_points,
    )


@router.get("/recommendations", response_model=MemoirRecommendationsResponse)
async def get_memoir_recommendations(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get recommendation scenarios for changing course."""
    repo = EntryRepository(db)
    recent = await repo.get_recent(user_id, limit=30)
    descriptions = " ".join((e.description or "") for e in recent).lower()

    recommendations: list[MemoirRecommendationItem] = [
        MemoirRecommendationItem(
            title="Сценарий: усилить стабильность",
            description="Добавь 1 фиксированную привычку утром и отслеживай 14 дней без пропусков.",
        ),
        MemoirRecommendationItem(
            title="Сценарий: изменить курс проекта",
            description="Сделай ветвление в виртуальном поле: успех / пауза / pivot и выбери триггер перехода.",
        ),
    ]

    if "стресс" in descriptions or "устал" in descriptions or "выгор" in descriptions:
        recommendations.append(
            MemoirRecommendationItem(
                title="Анти-выгорание",
                description="Сократи нагрузку на 20% и зафиксируй 3 события, которые возвращают энергию.",
            )
        )

    return MemoirRecommendationsResponse(items=recommendations)
