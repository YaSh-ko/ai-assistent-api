"""
Semantic Linker — creates Neo4j relationships between entities
based on embedding similarity via the AI service.

Flow:
1. API calls AI service POST /ai/similar-entities (ChromaDB + GigaChat embeddings)
2. AI service returns semantically similar entities with scores
3. API creates Neo4j relationships with appropriate types
"""
import logging
from typing import List

import httpx

from src.core.config import settings
from src.infrastructure.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.65
MAX_LINKS = 5

_RELATIONSHIP_MAP = {
    ("observation", "observation"): "RELATES_TO",
    ("observation", "goal"): "MOTIVATED",
    ("goal", "observation"): "MOTIVATED",
    ("observation", "task"): "DOCUMENTS",
    ("task", "observation"): "DOCUMENTS",
    ("goal", "task"): "DECOMPOSED_INTO",
    ("task", "goal"): "SUPPORTS",
    ("goal", "goal"): "RELATES_TO",
    ("task", "task"): "RELATES_TO",
}

_LABEL_MAP = {
    "observation": "Entry",
    "goal": "Goal",
    "task": "Experiment",
}


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
                "top_k": MAX_LINKS * 2,
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
    source_label = _LABEL_MAP.get(entity_type, "Entry")

    for candidate in candidates:
        candidate_id = candidate["entity_id"]
        candidate_type = candidate["entity_type"]
        candidate_title = candidate.get("title", "")
        score = candidate.get("score", 0)

        rel_type = _RELATIONSHIP_MAP.get((entity_type, candidate_type), "RELATES_TO")
        target_label = _LABEL_MAP.get(candidate_type, "Entry")

        try:
            await neo4j_client.execute_query_async(
                f"""
                MATCH (a:{source_label} {{id: $a_id, user_id: $user_id}})
                MATCH (b:{target_label} {{id: $b_id, user_id: $user_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                ON CREATE SET r.reason = $reason, r.score = $score, r.created_at = datetime()
                RETURN r
                """,
                {
                    "a_id": entity_id,
                    "b_id": candidate_id,
                    "user_id": user_id,
                    "reason": f"{title[:60]} \u2194 {candidate_title[:60]}",
                    "score": round(score, 3),
                },
            )
            link = {
                "from": entity_id,
                "to": candidate_id,
                "rel": rel_type,
                "score": round(score, 3),
                "target_title": candidate_title,
            }
            created_links.append(link)
            logger.info(
                "[SemanticLinker] Created: %s(%s) -[%s %.3f]-> %s(%s) '%s'",
                entity_type, entity_id[:8], rel_type, score,
                candidate_type, candidate_id[:8], candidate_title[:50],
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
