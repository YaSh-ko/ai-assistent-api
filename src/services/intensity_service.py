"""Intensity metrics derived from detector valence (-1..1 → -10..10)."""
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from common.database.models import IntensityMetric
from src.data.repositories.metrics import IntensityMetricRepository


def valence_to_intensity(valence: Optional[float]) -> Optional[float]:
    """Map detector valence (-1..1) to intensity_metrics.intensity_value (-10..10)."""
    if valence is None:
        return None
    try:
        v = float(valence)
    except (TypeError, ValueError):
        return None
    v = max(-1.0, min(1.0, v))
    return round(v * 10.0, 2)


async def record_entry_intensity(
    db: AsyncSession,
    *,
    user_id: str,
    entry_id: UUID,
    metric_date: date,
    valence: Optional[float],
    note: Optional[str] = None,
) -> Optional[IntensityMetric]:
    """Persist one intensity point for an observation (entry). Skips if valence is absent."""
    intensity_value = valence_to_intensity(valence)
    if intensity_value is None:
        return None

    metric = IntensityMetric(
        user_id=user_id,
        entity_type="entry",
        entity_id=entry_id,
        intensity_value=intensity_value,
        metric_date=metric_date,
        note=(note[:500] if note else None),
    )
    repo = IntensityMetricRepository(db)
    return await repo.create(metric)
