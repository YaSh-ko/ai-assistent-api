"""Unit tests for semantic_linker filtering rules."""
import pytest
from unittest.mock import AsyncMock, patch

from src.services.semantic_linker import (
    CHROMA_SEARCH_THRESHOLD,
    CROSS_TYPE_EMBEDDING_ONLY_THRESHOLD,
    CROSS_TYPE_SAME_AREA_THRESHOLD,
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

    def test_spending_vs_fatigue_no_false_prefix(self):
        assert not _has_topic_overlap(
            "Еще заметил что много трачу",
            "Усталость и прекращение занятий спортом",
        )

    def test_llm_boilerplate_descriptions_no_overlap(self):
        assert not _has_topic_overlap(
            "Пользователь чувствует усталость последние несколько недель и замечает снижение активности в спорте",
            "Пользователь заметил, что стал тратить значительно больше денег",
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
            "observation", "goal", 0.86,
            "Поздно ложусь", "Сдать IELTS",
        )

    def test_accepts_cross_type_observation_goal_with_overlap(self):
        assert _should_link(
            "goal", "observation", 0.86,
            "Завести дневник с задачами на неделю",
            "Усталость из-за невыполнения простых задач",
        )

    def test_accepts_cross_type_thematic_without_shared_words(self):
        assert _should_link(
            "goal", "observation", CROSS_TYPE_EMBEDDING_ONLY_THRESHOLD,
            "Хочу больше денег и стабильный доход",
            "Нашёл подработку на вечерах",
        )

    def test_rejects_cross_type_below_threshold(self):
        assert not _should_link(
            "goal", "observation", CROSS_TYPE_THRESHOLD - 0.01,
            "Завести дневник с задачами",
            "Усталость из-за невыполнения задач",
        )

    def test_rejects_same_type_without_overlap(self):
        assert not _should_link(
            "observation", "observation", 0.94,
            "Стал много пить кофе",
            "Последние дни долго не могу уснуть",
        )

    def test_rejects_same_type_below_search_threshold(self):
        assert not _should_link(
            "observation", "observation", SIMILARITY_THRESHOLD - 0.01,
            "Поздно ложусь", "Сдать IELTS",
        )

    def test_accepts_same_type_with_overlap(self):
        assert _should_link(
            "observation", "observation", SIMILARITY_THRESHOLD,
            "Ложусь после полуночи", "После полуночи не могу уснуть",
        )

    def test_rejects_unrelated_same_type_even_at_high_score(self):
        assert not _should_link(
            "observation", "observation", 0.94,
            "Усталость и прекращение занятий спортом",
            "Заметил увеличение заработка на проекте",
        )

    def test_rejects_cross_type_spending_vs_fatigue_without_overlap(self):
        assert not _should_link(
            "observation", "goal", 0.90,
            "Ещё заметил что много трачу на еду и подписки",
            "Усталость и прекращение занятий спортом",
        )

    def test_rejects_obs_obs_different_life_areas(self):
        assert not _should_link(
            "observation", "observation", 0.94,
            "Много трачу на подписки",
            "Усталость и снижение активности в спорте",
            "finance",
            "health",
        )

    def test_accepts_goal_obs_same_health_area(self):
        assert _should_link(
            "goal", "observation", CROSS_TYPE_SAME_AREA_THRESHOLD,
            "Вернуться к регулярным тренировкам три раза в неделю",
            "Усталость и снижение активности в спорте",
            "health",
            "health",
        )

    def test_accepts_goal_obs_same_health_area_typical_chroma_score(self):
        """Типичный score obs↔goal в Chroma (~0.83) при одной теме."""
        assert _should_link(
            "goal", "observation", 0.827,
            "Возврат к регулярным тренировкам",
            "Усталость и прекращение занятий спортом",
            "health",
            "health",
        )

    def test_chroma_search_threshold_below_link_threshold(self):
        assert CHROMA_SEARCH_THRESHOLD < SIMILARITY_THRESHOLD

    def test_rejects_cross_type_embedding_only_below_new_threshold(self):
        assert not _should_link(
            "goal", "observation", 0.90,
            "Хочу больше денег и стабильный доход",
            "Усталость из-за перегрузки на работе",
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
                "score": 0.86,
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
                "score": 0.86,
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
