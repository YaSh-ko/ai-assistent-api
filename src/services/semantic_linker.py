"""
Semantic Linker — creates Neo4j relationships between entities
based on embedding similarity via the AI service.

Same-type: obs↔obs, goal↔goal, task↔task (RELATES_TO).
Cross-type: observation→goal only, with stricter score + lexical overlap.
"""
import logging
import re
from typing import List, Optional, Set, Tuple

import httpx

from src.core.config import settings
from src.infrastructure.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.78
CROSS_TYPE_THRESHOLD = 0.80
VERY_HIGH_CONFIDENCE_THRESHOLD = 0.92
MAX_LINKS = 3

_SHORT_PREFIX_BLOCK = frozenset({
    "по", "на", "не", "ни", "от", "до", "из", "за", "при", "со", "во", "об",
})

_ALLOWED_SAME_TYPE_PAIRS: Set[Tuple[str, str]] = {
    ("observation", "observation"),
    ("goal", "goal"),
    ("task", "task"),
}

# Cross-type pairs allowed when lexical overlap confirms the theme.
_ALLOWED_CROSS_TYPE_PAIRS: Set[frozenset[str]] = {
    frozenset({"observation", "goal"}),
}

_RELATIONSHIP_MAP = {
    ("observation", "observation"): "RELATES_TO",
    ("goal", "goal"): "RELATES_TO",
    ("task", "task"): "RELATES_TO",
    frozenset({"observation", "goal"}): "RELATES_TO",
}

_LABEL_MAP = {
    "observation": "Entry",
    "goal": "Goal",
    "task": "Experiment",
}

_RU_STOP = frozenset({
    "когда", "чтобы", "после", "перед", "через", "который", "которая", "которые",
    "этого", "этом", "этот", "эта", "была", "было", "были", "будет", "буду",
    "очень", "просто", "только", "уже", "ещё", "еще", "если", "или", "либо",
    "что", "как", "для", "при", "над", "под", "без", "мне", "меня", "себя",
    "свой", "своей", "сегодня", "вчера", "завтра", "теперь", "хочу", "надо",
    "нужно", "могу", "мог", "был", "была", "есть", "был", "были", "этой",
    "the", "and", "for", "with", "that", "this", "have", "from", "want",
})


def _tokenize(text: str) -> Set[str]:
    words = re.findall(r"[\w\u0400-\u04FF]+", (text or "").lower())
    return {w for w in words if len(w) >= 3 and w not in _RU_STOP}


def _has_topic_overlap(text_a: str, text_b: str) -> bool:
    """
    Lexical overlap between entity texts.
    Blocks cross-topic false positives from embedding similarity alone.
    """
    ta = _tokenize(text_a)
    tb = _tokenize(text_b)
    combined_a = (text_a or "").lower()
    combined_b = (text_b or "").lower()

    shared = ta & tb
    if len(shared) >= 2:
        return True
    if len(shared) == 1 and any(len(w) >= 5 for w in shared):
        return True

    for wa in ta:
        for wb in tb:
            if len(wa) >= 4 and len(wb) >= 4 and wa[:3] == wb[:3]:
                return True
            if len(wa) >= 3 and len(wb) >= 3:
                prefix = wa[:2]
                if prefix == wb[:2] and prefix not in _SHORT_PREFIX_BLOCK:
                    return True

    for w in ta:
        if len(w) >= 4 and w in combined_b:
            return True
    for w in tb:
        if len(w) >= 4 and w in combined_a:
            return True

    return False


def _is_cross_type_pair(entity_type: str, candidate_type: str) -> bool:
    return frozenset({entity_type, candidate_type}) in _ALLOWED_CROSS_TYPE_PAIRS


def _should_link(
    entity_type: str,
    candidate_type: str,
    score: float,
    source_text: str,
    candidate_text: str,
) -> bool:
    pair = (entity_type, candidate_type)
    cross_type = _is_cross_type_pair(entity_type, candidate_type)

    if pair not in _ALLOWED_SAME_TYPE_PAIRS and not cross_type:
        logger.debug(
            "[SemanticLinker] Skip disallowed pair %s (score=%.3f)",
            pair, score,
        )
        return False

    min_score = CROSS_TYPE_THRESHOLD if cross_type else SIMILARITY_THRESHOLD
    if score < min_score:
        return False

    if cross_type:
        return _has_topic_overlap(source_text, candidate_text)

    if _has_topic_overlap(source_text, candidate_text):
        return True
    return score >= VERY_HIGH_CONFIDENCE_THRESHOLD


def _resolve_link_direction(
    entity_type: str,
    candidate_type: str,
    entity_id: str,
    candidate_id: str,
) -> Tuple[str, str, str, str]:
    """
    Return (from_label, from_id, to_label, to_id) for Neo4j MERGE.
    Observation→goal links always point Entry → Goal.
    """
    if frozenset({entity_type, candidate_type}) == frozenset({"observation", "goal"}):
        if entity_type == "observation":
            obs_id, goal_id = entity_id, candidate_id
        else:
            obs_id, goal_id = candidate_id, entity_id
        return "Entry", obs_id, "Goal", goal_id

    from_label = _LABEL_MAP.get(entity_type, "Entry")
    to_label = _LABEL_MAP.get(candidate_type, "Entry")
    return from_label, entity_id, to_label, candidate_id


async def _find_similar(
    user_id: str,
    query_text: str,
    exclude_id: str,
) -> List[dict]:
    """Call AI service to find semantically similar entities."""
    url = f"{settings.AI_SERVICE_URL}/api/v1/ai/similar-entities"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json={
                "user_id": user_id,
                "query_text": query_text,
                "exclude_id": exclude_id,
                "top_k": MAX_LINKS * 3,
                "threshold": SIMILARITY_THRESHOLD,
            })
            resp.raise_for_status()
            return resp.json().get("items", [])
    except httpx.ConnectError:
        logger.warning("[SemanticLinker] AI service unavailable at %s", url)
        return []
    except Exception as e:
        logger.warning("[SemanticLinker] AI service call failed: %s", e)
        return []


async def cleanup_embedding_links(user_id: str) -> dict:
    """
    Remove auto-generated semantic links that are cross-type, below threshold,
    or any prior embedding-scored RELATES_TO (so backfill can recreate with current rules).
    Structural links (goal→task without score) are preserved.
    """
    stats = {"cross_type": 0, "low_score": 0, "scored_relates_to": 0}

    scored_result = await neo4j_client.execute_query_async(
        """
        MATCH (a {user_id: $user_id})-[r:RELATES_TO]->(b {user_id: $user_id})
        WHERE r.score IS NOT NULL
        WITH r
        DELETE r
        RETURN count(*) AS deleted
        """,
        {"user_id": user_id},
    )
    if scored_result:
        stats["scored_relates_to"] = scored_result[0].get("deleted", 0)

    cross_type_result = await neo4j_client.execute_query_async(
        """
        MATCH (a {user_id: $user_id})-[r]->(b {user_id: $user_id})
        WHERE r.score IS NOT NULL
          AND NOT (
            (a:Entry AND b:Entry) OR
            (a:Goal AND b:Goal) OR
            (a:Experiment AND b:Experiment) OR
            (a:Entry AND b:Goal)
          )
        WITH r
        DELETE r
        RETURN count(*) AS deleted
        """,
        {"user_id": user_id},
    )
    if cross_type_result:
        stats["cross_type"] = cross_type_result[0].get("deleted", 0)

    low_score_result = await neo4j_client.execute_query_async(
        """
        MATCH (a {user_id: $user_id})-[r]->(b {user_id: $user_id})
        WHERE r.score IS NOT NULL AND r.score < $min_score
        WITH r
        DELETE r
        RETURN count(*) AS deleted
        """,
        {"user_id": user_id, "min_score": SIMILARITY_THRESHOLD},
    )
    if low_score_result:
        stats["low_score"] = low_score_result[0].get("deleted", 0)

    logger.info("[SemanticLinker] Cleanup for user %s: %s", user_id, stats)
    return stats


async def semantic_link_entity(
    entity_id: str,
    entity_type: str,
    title: str,
    description: str,
    user_id: str,
    db=None,
) -> List[dict]:
    """
    Find semantically similar entities via AI service embeddings
    and create Neo4j relationships.
    """
    query_text = f"{title} {description}".strip()
    if not query_text:
        return []

    candidates = await _find_similar(user_id, query_text, entity_id)

    if not candidates:
        logger.info("[SemanticLinker] No similar entities for %s '%s'", entity_type, title[:60])
        return []

    logger.info(
        "[SemanticLinker] Found %d candidates for %s '%s'",
        len(candidates), entity_type, title[:60],
    )

    created_links: List[dict] = []

    for candidate in candidates:
        candidate_id = candidate["entity_id"]
        candidate_type = candidate["entity_type"]
        candidate_title = candidate.get("title", "")
        candidate_description = candidate.get("description", "")
        candidate_text = f"{candidate_title} {candidate_description}".strip()
        score = candidate.get("score", 0)

        if not _should_link(entity_type, candidate_type, score, query_text, candidate_text):
            logger.info(
                "[SemanticLinker] Rejected: %s(%s) -> %s(%s) score=%.3f",
                entity_type, entity_id[:8], candidate_type, candidate_id[:8], score,
            )
            continue

        type_key = frozenset({entity_type, candidate_type})
        rel_type = _RELATIONSHIP_MAP.get(
            (entity_type, candidate_type),
            _RELATIONSHIP_MAP.get(type_key, "RELATES_TO"),
        )
        from_label, from_id, to_label, to_id = _resolve_link_direction(
            entity_type, candidate_type, entity_id, candidate_id,
        )

        try:
            await neo4j_client.execute_query_async(
                f"""
                MATCH (a:{from_label} {{id: $a_id, user_id: $user_id}})
                MATCH (b:{to_label} {{id: $b_id, user_id: $user_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                ON CREATE SET r.reason = $reason, r.score = $score, r.created_at = datetime()
                ON MATCH SET r.score = $score
                RETURN r
                """,
                {
                    "a_id": from_id,
                    "b_id": to_id,
                    "user_id": user_id,
                    "reason": f"{title[:60]} \u2194 {candidate_title[:60]}",
                    "score": round(score, 3),
                },
            )
            link = {
                "from": from_id,
                "to": to_id,
                "rel": rel_type,
                "score": round(score, 3),
                "target_title": candidate_title,
            }
            created_links.append(link)
            logger.info(
                "[SemanticLinker] Created: %s(%s) -[%s %.3f]-> %s(%s) '%s'",
                from_label, from_id[:8], rel_type, score,
                to_label, to_id[:8], candidate_title[:50],
            )

            if len(created_links) >= MAX_LINKS:
                break

        except Exception as e:
            logger.warning("[SemanticLinker] Neo4j link failed: %s", e)

    logger.info(
        "[SemanticLinker] Done for %s '%s': %d links created",
        entity_type, title[:50], len(created_links),
    )
    return created_links
