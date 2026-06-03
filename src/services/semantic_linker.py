"""
Semantic Linker — creates Neo4j relationships between entities
based on embedding similarity via the AI service.

Uses title (+ life_area from detector) for embedding search.
Lexical overlap and life_area block cross-topic false positives.
"""
import logging
import re
import time
from typing import List, Optional, Set, Tuple

import httpx

from src.core.config import settings
from src.infrastructure.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)

# Порог создания связи (после правил area/overlap)
SIMILARITY_THRESHOLD = 0.84
CROSS_TYPE_THRESHOLD = 0.82
CROSS_TYPE_EMBEDDING_ONLY_THRESHOLD = 0.91
# obs↔goal с одним life_area (разные формулировки, score ~0.82–0.88)
CROSS_TYPE_SAME_AREA_THRESHOLD = 0.82
# Порог только для выборки кандидатов из Chroma (ниже — отсекает до линкера)
CHROMA_SEARCH_THRESHOLD = 0.72
MAX_LINKS = 3

_VALID_AREAS = frozenset({
    "career", "health", "skills", "relationships", "finance", "personal", "other",
})
_AREA_WILDCARDS = frozenset({"personal", "other"})

_ALLOWED_SAME_TYPE_PAIRS: Set[Tuple[str, str]] = {
    ("observation", "observation"),
    ("goal", "goal"),
    ("task", "task"),
}

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
    # шаблонные формулировки в описаниях от LLM/детектора
    "пользователь", "пользователя", "заметил", "замечает", "замечаю", "чувствует",
    "чувствую", "стал", "стала", "стали", "несколько", "последние", "недель",
    "недели", "значительно", "больше", "привело", "настроения", "активности",
})


def _normalize_area(area: Optional[str]) -> Optional[str]:
    if not area:
        return None
    a = area.strip().lower()
    return a if a in _VALID_AREAS else "other"


def _areas_compatible(area_a: Optional[str], area_b: Optional[str]) -> bool:
    a, b = _normalize_area(area_a), _normalize_area(area_b)
    if not a or not b:
        return True
    if a == b:
        return True
    if a in _AREA_WILDCARDS or b in _AREA_WILDCARDS:
        return True
    return False


def _embedding_query(title: str, description: str, area: Optional[str]) -> str:
    """Поиск по заголовку и теме; описание — только если заголовка нет."""
    t = (title or "").strip()
    if not t:
        t = (description or "").strip()[:200]
    a = _normalize_area(area)
    return f"[{a}] {t}" if a else t


def _overlap_text(title: str, description: str) -> str:
    t = (title or "").strip()
    d = (description or "").strip()
    if not d or d == t:
        return t
    return f"{t} {d[:280]}"


def _tokenize(text: str) -> Set[str]:
    words = re.findall(r"[\w\u0400-\u04FF]+", (text or "").lower())
    return {w for w in words if len(w) >= 3 and w not in _RU_STOP}


def _topic_overlap_detail(text_a: str, text_b: str) -> Tuple[bool, Set[str]]:
    ta = _tokenize(text_a)
    tb = _tokenize(text_b)
    if not ta or not tb:
        return False, set()

    shared = ta & tb
    if len(shared) >= 2:
        return True, shared
    if len(shared) == 1 and any(len(w) >= 5 for w in shared):
        return True, shared

    combined_a = (text_a or "").lower()
    combined_b = (text_b or "").lower()
    for w in ta:
        if len(w) >= 6 and w in combined_b:
            return True, {w}
    for w in tb:
        if len(w) >= 6 and w in combined_a:
            return True, {w}

    return False, shared


def _has_topic_overlap(text_a: str, text_b: str) -> bool:
    ok, _ = _topic_overlap_detail(text_a, text_b)
    return ok


def _is_cross_type_pair(entity_type: str, candidate_type: str) -> bool:
    return frozenset({entity_type, candidate_type}) in _ALLOWED_CROSS_TYPE_PAIRS


def _evaluate_link(
    entity_type: str,
    candidate_type: str,
    score: float,
    source_text: str,
    candidate_text: str,
    entity_area: Optional[str] = None,
    candidate_area: Optional[str] = None,
) -> Tuple[bool, str]:
    """Возвращает (создавать_связь, причина_решения) для логов."""
    pair = (entity_type, candidate_type)
    cross_type = _is_cross_type_pair(entity_type, candidate_type)
    norm_a = _normalize_area(entity_area)
    norm_b = _normalize_area(candidate_area)

    if not _areas_compatible(entity_area, candidate_area):
        return False, f"life_area_mismatch:{norm_a or '?'} vs {norm_b or '?'}"

    if pair not in _ALLOWED_SAME_TYPE_PAIRS and not cross_type:
        return False, f"pair_not_allowed:{entity_type}+{candidate_type}"

    min_score = CROSS_TYPE_THRESHOLD if cross_type else SIMILARITY_THRESHOLD
    if score < min_score:
        return False, f"score_below_min:{score:.3f}<{min_score:.2f}"

    same_area = bool(norm_a and norm_b and norm_a == norm_b)
    overlap_ok, shared_tokens = _topic_overlap_detail(source_text, candidate_text)
    shared_preview = ",".join(sorted(shared_tokens)[:6]) if shared_tokens else "-"

    if cross_type:
        if same_area and score >= CROSS_TYPE_SAME_AREA_THRESHOLD:
            return True, (
                f"cross_type_same_area:{norm_a} score={score:.3f}"
                f">={CROSS_TYPE_SAME_AREA_THRESHOLD}"
            )
        if score >= CROSS_TYPE_EMBEDDING_ONLY_THRESHOLD:
            return True, (
                f"cross_type_high_embedding:{score:.3f}"
                f">={CROSS_TYPE_EMBEDDING_ONLY_THRESHOLD}"
            )
        if overlap_ok:
            return True, f"cross_type_lexical_overlap:[{shared_preview}]"
        return False, (
            f"cross_type_no_overlap:shared=[{shared_preview}] "
            f"need_score>={CROSS_TYPE_EMBEDDING_ONLY_THRESHOLD:.2f} or same_area"
        )

    if overlap_ok:
        return True, f"same_type_lexical_overlap:[{shared_preview}]"
    return False, f"same_type_no_overlap:shared=[{shared_preview}]"


def _should_link(
    entity_type: str,
    candidate_type: str,
    score: float,
    source_text: str,
    candidate_text: str,
    entity_area: Optional[str] = None,
    candidate_area: Optional[str] = None,
) -> bool:
    ok, _ = _evaluate_link(
        entity_type,
        candidate_type,
        score,
        source_text,
        candidate_text,
        entity_area,
        candidate_area,
    )
    return ok


def _resolve_link_direction(
    entity_type: str,
    candidate_type: str,
    entity_id: str,
    candidate_id: str,
) -> Tuple[str, str, str, str]:
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
    url = f"{settings.AI_SERVICE_URL}/api/v1/ai/similar-entities"
    payload = {
        "user_id": user_id,
        "query_text": query_text,
        "exclude_id": exclude_id,
        "top_k": MAX_LINKS * 5,
        "threshold": CHROMA_SEARCH_THRESHOLD,
    }
    logger.info(
        "[SemanticLinker] Chroma search: user=%s exclude=%s "
        "search_threshold=%.2f link_threshold=%.2f query=%r",
        user_id,
        (exclude_id or "")[:8] or "-",
        CHROMA_SEARCH_THRESHOLD,
        SIMILARITY_THRESHOLD,
        query_text[:120],
    )
    try:
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            resp.raise_for_status()
            items = resp.json().get("items", [])
            logger.info(
                "[SemanticLinker] AI similar-entities HTTP %s in %.0fms -> %d items "
                "(top_k=%d search_thr=%.2f)",
                resp.status_code,
                elapsed_ms,
                len(items),
                payload["top_k"],
                CHROMA_SEARCH_THRESHOLD,
            )
            for i, item in enumerate(items, start=1):
                logger.info(
                    "[SemanticLinker]   #%d score=%.3f [%s] id=%s area=%s title=%r",
                    i,
                    float(item.get("score", 0)),
                    item.get("entity_type", "?"),
                    str(item.get("entity_id", ""))[:8],
                    item.get("life_area") or "-",
                    (item.get("title") or "")[:50],
                )
            return items
    except httpx.ConnectError:
        logger.warning("[SemanticLinker] AI service unavailable at %s", url)
        return []
    except Exception as e:
        logger.warning("[SemanticLinker] AI service call failed: %s", e, exc_info=True)
        return []


async def cleanup_embedding_links(user_id: str) -> dict:
    logger.info(
        "[SemanticLinker] === Cleanup start === user=%s "
        "(remove scored RELATES_TO, invalid cross-type, score<%s)",
        user_id,
        SIMILARITY_THRESHOLD,
    )
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
    logger.info(
        "[SemanticLinker] Cleanup step 1: deleted %d scored RELATES_TO",
        stats["scored_relates_to"],
    )

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
    logger.info(
        "[SemanticLinker] Cleanup step 2: deleted %d invalid cross-type scored links",
        stats["cross_type"],
    )

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
    logger.info(
        "[SemanticLinker] Cleanup step 3: deleted %d low-score links",
        stats["low_score"],
    )

    logger.info("[SemanticLinker] === Cleanup done === user=%s stats=%s", user_id, stats)
    return stats


async def semantic_link_entity(
    entity_id: str,
    entity_type: str,
    title: str,
    description: str,
    user_id: str,
    db=None,
    life_area: Optional[str] = None,
) -> List[dict]:
    logger.info(
        "[SemanticLinker] === Link pass start === id=%s type=%s area=%s user=%s title=%r",
        entity_id[:8],
        entity_type,
        _normalize_area(life_area) or "-",
        user_id,
        (title or "")[:80],
    )
    logger.info(
        "[SemanticLinker] Policy: search_thr=%.2f link_thr=%.2f cross_type=%.2f "
        "same_area=%.2f embed_only=%.2f max_links=%d",
        CHROMA_SEARCH_THRESHOLD,
        SIMILARITY_THRESHOLD,
        CROSS_TYPE_THRESHOLD,
        CROSS_TYPE_SAME_AREA_THRESHOLD,
        CROSS_TYPE_EMBEDDING_ONLY_THRESHOLD,
        MAX_LINKS,
    )

    if entity_type == "task":
        logger.info(
            "[SemanticLinker] Skip task id=%s (tasks use DECOMPOSED_INTO, not semantic RELATES_TO)",
            entity_id[:8],
        )
        return []

    query_text = _embedding_query(title, description, life_area)
    if not query_text:
        logger.info("[SemanticLinker] Skip: empty embedding query (no title/area)")
        return []

    source_overlap = _overlap_text(title, description)
    logger.info(
        "[SemanticLinker] Embedding query=%r | overlap_text=%r",
        query_text[:120],
        source_overlap[:120],
    )

    candidates = await _find_similar(user_id, query_text, entity_id)

    if not candidates:
        logger.info(
            "[SemanticLinker] No Chroma candidates for %s id=%s",
            entity_type,
            entity_id[:8],
        )
        return []

    created_links: List[dict] = []
    rejected = 0

    for candidate in candidates:
        candidate_id = candidate["entity_id"]
        candidate_type = candidate["entity_type"]
        candidate_title = candidate.get("title", "")
        candidate_description = candidate.get("description", "")
        candidate_area = candidate.get("life_area")
        candidate_overlap = _overlap_text(candidate_title, candidate_description)
        score = candidate.get("score", 0)

        accept, reason = _evaluate_link(
            entity_type,
            candidate_type,
            score,
            source_overlap,
            candidate_overlap,
            life_area,
            candidate_area,
        )

        if not accept:
            rejected += 1
            _, shared = _topic_overlap_detail(source_overlap, candidate_overlap)
            shared_preview = ",".join(sorted(shared)[:8]) if shared else "-"
            logger.info(
                "[SemanticLinker] REJECT %s(%s) -> %s(%s) score=%.3f | %s | "
                "areas=%s/%s | shared_tokens=[%s] | src=%r | cand=%r",
                entity_type,
                entity_id[:8],
                candidate_type,
                candidate_id[:8],
                score,
                reason,
                _normalize_area(life_area) or "-",
                _normalize_area(candidate_area) or "-",
                shared_preview,
                source_overlap[:80],
                candidate_overlap[:80],
            )
            continue

        _, shared = _topic_overlap_detail(source_overlap, candidate_overlap)
        shared_preview = ",".join(sorted(shared)[:8]) if shared else "-"
        logger.info(
            "[SemanticLinker] ACCEPT %s(%s) -> %s(%s) score=%.3f | %s | shared=[%s]",
            entity_type,
            entity_id[:8],
            candidate_type,
            candidate_id[:8],
            score,
            reason,
            shared_preview,
        )

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
                logger.info(
                    "[SemanticLinker] Max links (%d) reached, stop evaluating candidates",
                    MAX_LINKS,
                )
                break

        except Exception as e:
            logger.warning(
                "[SemanticLinker] Neo4j MERGE failed %s(%s)->%s(%s): %s",
                from_label,
                from_id[:8],
                to_label,
                to_id[:8],
                e,
                exc_info=True,
            )

    if created_links:
        for link in created_links:
            logger.info(
                "[SemanticLinker]   link: %s -> %s score=%.3f '%s'",
                link["from"][:8],
                link["to"][:8],
                link["score"],
                (link.get("target_title") or "")[:50],
            )
    logger.info(
        "[SemanticLinker] === Link pass done === id=%s type=%s | "
        "candidates=%d rejected=%d created=%d",
        entity_id[:8],
        entity_type,
        len(candidates),
        rejected,
        len(created_links),
    )
    return created_links
