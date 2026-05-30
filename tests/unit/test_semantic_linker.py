"""Unit tests for semantic_linker filtering rules."""
import pytest
from unittest.mock import AsyncMock, patch

from src.services.semantic_linker import (
    CROSS_TYPE_THRESHOLD,
    SIMILARITY_THRESHOLD,
    _has_topic_overlap,
    _resolve_link_direction,
    _should_link,
    cleanup_embedding_links,
    semantic_link_entity,
)


class TestTopicOverlap:
    def test_unrelated_topics_no_overlap(self):
        assert not _has_topic_overlap(
            "Ложусь после полуночи уже вторую неделю",
            "Сдать IELTS на 7.0 к сентябрю",
        )

    def test_related_sleep_topics_overlap(self):
        assert _has_topic_overlap(
            "Ложусь после полуночи уже вторую неделю",
            "После позднего сна днём тяжело концентрироваться",
        )

    def test_shared_specific_term(self):
        assert _has_topic_overlap(
            "Пробный тест IELTS speaking",
            "Цель: сдать IELTS на 7.0",
        )


class TestShouldLink:
    def test_rejects_cross_type_observation_goal_without_overlap(self):
        assert not _should_link(
            "observation", "goal", 0.82,
            "Поздно ложусь", "Сдать IELTS",
        )

    def test_accepts_cross_type_observation_goal_with_overlap(self):
        assert _should_link(
            "goal", "observation", 0.841,
            "Завести дневник с задачами на неделю",
            "Усталость из-за невыполнения простых задач",
        )

    def test_rejects_cross_type_below_threshold(self):
        assert not _should_link(
            "goal", "observation", CROSS_TYPE_THRESHOLD - 0.01,
            "Завести дневник с задачами",
            "Усталость из-за невыполнения задач",
        )

    def test_rejects_same_type_without_overlap_and_low_score(self):
        assert not _should_link(
            "observation", "observation", 0.79,
            "Поздно ложусь", "Сдать IELTS",
        )

    def test_accepts_same_type_with_overlap(self):
        assert _should_link(
            "observation", "observation", 0.80,
            "Ложусь после полуночи", "После полуночи не могу уснуть",
        )

    def test_accepts_very_high_confidence_without_overlap(self):
        assert _should_link(
            "observation", "observation", 0.93,
            "Бессонница", "Не могу уснуть",
        )

    def test_rejects_high_confidence_without_overlap(self):
        assert not _should_link(
            "observation", "observation", 0.86,
            "Поздний сон перед встречей",
            "Устал, не успел постирать вещи с Wildberries",
        )

    def test_related_topics_via_prefix_overlap(self):
        assert _has_topic_overlap(
            "Ложусь поздно",
            "Поздний сон перед встречей",
        )

    def test_rejects_below_threshold(self):
        assert not _should_link(
            "goal", "goal", SIMILARITY_THRESHOLD - 0.01,
            "IELTS 7.0", "IELTS 7.0",
        )


def test_cross_type_link_direction_goal_to_observation():
    from_label, from_id, to_label, to_id = _resolve_link_direction(
        "goal", "observation", "goal-1", "entry-1",
    )
    assert (from_label, from_id, to_label, to_id) == ("Entry", "entry-1", "Goal", "goal-1")


@pytest.mark.asyncio
async def test_semantic_link_entity_skips_unrelated_cross_type_candidates():
    with patch("src.services.semantic_linker._find_similar", new_callable=AsyncMock) as find:
        find.return_value = [
            {
                "entity_id": "goal-1",
                "entity_type": "goal",
                "title": "Сдать IELTS",
                "description": "Балл 7.0",
                "score": 0.82,
            },
        ]
        with patch("src.services.semantic_linker.neo4j_client") as neo:
            neo.execute_query_async = AsyncMock()
            links = await semantic_link_entity(
                entity_id="entry-1",
                entity_type="observation",
                title="Поздно ложусь",
                description="После полуночи",
                user_id="user-1",
            )
    assert links == []
    neo.execute_query_async.assert_not_called()


@pytest.mark.asyncio
async def test_semantic_link_entity_links_related_observation_to_goal():
    with patch("src.services.semantic_linker._find_similar", new_callable=AsyncMock) as find:
        find.return_value = [
            {
                "entity_id": "entry-1",
                "entity_type": "observation",
                "title": "Усталость из-за невыполнения простых задач",
                "description": "",
                "score": 0.841,
            },
        ]
        with patch("src.services.semantic_linker.neo4j_client") as neo:
            neo.execute_query_async = AsyncMock(return_value=[{"r": {}}])
            links = await semantic_link_entity(
                entity_id="goal-1",
                entity_type="goal",
                title="Завести дневник с задачами на неделю",
                description="Планирование задач",
                user_id="user-1",
            )
    assert len(links) == 1
    assert links[0]["from"] == "entry-1"
    assert links[0]["to"] == "goal-1"
    neo.execute_query_async.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_embedding_links():
    with patch("src.services.semantic_linker.neo4j_client") as neo:
        neo.execute_query_async = AsyncMock(side_effect=[
            [{"deleted": 5}],
            [{"deleted": 3}],
            [{"deleted": 1}],
        ])
        stats = await cleanup_embedding_links("user-1")
    assert stats == {"cross_type": 3, "low_score": 1, "scored_relates_to": 5}
    assert neo.execute_query_async.call_count == 3
