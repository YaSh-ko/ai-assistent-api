"""
Repository for intensity metrics.
"""
from typing import List, Optional
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID

from common.database.models import IntensityMetric
from .base import BaseRepository


class IntensityMetricRepository(BaseRepository[IntensityMetric]):
    """Repository for intensity metric operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(IntensityMetric, db)
    
    async def get_by_entity(
        self, 
        entity_type: str, 
        entity_id: UUID
    ) -> List[IntensityMetric]:
        """Get metrics by entity type and ID."""
        result = await self.db.execute(
            select(IntensityMetric)
            .where(
                IntensityMetric.entity_type == entity_type,
                IntensityMetric.entity_id == entity_id
            )
            .order_by(IntensityMetric.metric_date)
        )
        return list(result.scalars().all())
    
    async def get_average_intensity(
        self, 
        entity_type: str, 
        entity_id: UUID
    ) -> float:
        """Calculate average intensity for an entity."""
        from sqlalchemy import func
        
        result = await self.db.execute(
            select(func.avg(IntensityMetric.intensity_value))
            .where(
                IntensityMetric.entity_type == entity_type,
                IntensityMetric.entity_id == entity_id
            )
        )
        avg = result.scalar()
        return float(avg) if avg is not None else 0.0

    def _period_start(self, period: str) -> date:
        today = date.today()
        if period == "week":
            return today - timedelta(days=7)
        if period == "month":
            return today - timedelta(days=30)
        if period == "year":
            return today - timedelta(days=365)
        return today - timedelta(days=30)

    async def get_by_entity_since(
        self,
        entity_type: str,
        entity_id: UUID,
        since: date,
    ) -> List[IntensityMetric]:
        result = await self.db.execute(
            select(IntensityMetric)
            .where(
                and_(
                    IntensityMetric.entity_type == entity_type,
                    IntensityMetric.entity_id == entity_id,
                    IntensityMetric.metric_date >= since,
                )
            )
            .order_by(IntensityMetric.metric_date)
        )
        return list(result.scalars().all())

    async def get_by_entity_period(
        self,
        entity_type: str,
        entity_id: UUID,
        period: str,
    ) -> List[IntensityMetric]:
        """Метрики с даты начала периода (week/month/year) до сегодня."""
        since = self._period_start(period)
        return await self.get_by_entity_since(entity_type, entity_id, since)

    async def get_average_intensity_for_metrics(self, metrics: List[IntensityMetric]) -> Optional[float]:
        if not metrics:
            return None
        return sum(m.intensity_value for m in metrics) / len(metrics)
