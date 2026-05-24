"""
Markdown import endpoints.
"""
from typing import Annotated, List, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user_id
from src.api.v1.schemas.imports import (
    MarkdownImportRequest,
    MarkdownImportResponse,
    CreatedEntityRef,
)
from src.core.database import get_db
from src.services.entry_service import create_entry_and_sync
from src.services.goal_service import create_goal_and_sync
from src.services.experiment_service import create_experiment_and_sync

router = APIRouter()

SectionName = Literal["entries", "goals", "experiments"]


def _normalize_line(line: str) -> str:
    return line.strip()


def _detect_section(line: str) -> SectionName | None:
    lowered = line.lower().strip("# ").strip()
    if lowered in {"entries", "entry", "события", "записи"}:
        return "entries"
    if lowered in {"goals", "goal", "цели", "цель"}:
        return "goals"
    if lowered in {"experiments", "experiment", "эксперименты", "эксперимент"}:
        return "experiments"
    return None


def _strip_bullet_prefix(line: str) -> str:
    text = line.strip()
    for prefix in ("- ", "* ", "• ", "+ "):
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def _parse_markdown_sections(markdown: str) -> dict[SectionName, List[str]]:
    sections: dict[SectionName, List[str]] = {
        "entries": [],
        "goals": [],
        "experiments": [],
    }
    current_section: SectionName = "entries"

    for raw_line in markdown.splitlines():
        line = _normalize_line(raw_line)
        if not line:
            continue

        detected = _detect_section(line)
        if detected is not None:
            current_section = detected
            continue

        value = _strip_bullet_prefix(line)
        if value:
            sections[current_section].append(value)

    return sections


@router.post("/markdown", response_model=MarkdownImportResponse)
async def import_markdown(
    request: MarkdownImportRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Import markdown into entries/goals/experiments."""
    sections = _parse_markdown_sections(request.markdown)
    created_entities: List[CreatedEntityRef] = []

    if request.create_entries:
        for text in sections["entries"]:
            created = await create_entry_and_sync(
                db=db,
                user_id=user_id,
                title=text[:120],
                description=text,
                event_date=request.event_date,
            )
            created_entities.append(
                CreatedEntityRef(
                    id=str(created.id),
                    title=created.title or text[:120],
                    entity_type="entry",
                )
            )

    if request.create_goals:
        for text in sections["goals"]:
            try:
                created = await create_goal_and_sync(
                    db=db,
                    user_id=user_id,
                    title=text[:160],
                    description=text,
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to import goal: {str(e)}",
                )
            created_entities.append(
                CreatedEntityRef(
                    id=str(created.id),
                    title=created.title or text[:160],
                    entity_type="goal",
                )
            )

    if request.create_experiments:
        for text in sections["experiments"]:
            try:
                created = await create_experiment_and_sync(
                    db=db,
                    user_id=user_id,
                    title=text[:160],
                    description=text,
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to import experiment: {str(e)}",
                )
            created_entities.append(
                CreatedEntityRef(
                    id=str(created.id),
                    title=created.title or text[:160],
                    entity_type="experiment",
                )
            )

    entries_created = len([e for e in created_entities if e.entity_type == "entry"])
    goals_created = len([e for e in created_entities if e.entity_type == "goal"])
    experiments_created = len([e for e in created_entities if e.entity_type == "experiment"])

    return MarkdownImportResponse(
        entries_created=entries_created,
        goals_created=goals_created,
        experiments_created=experiments_created,
        created_entities=created_entities,
    )
