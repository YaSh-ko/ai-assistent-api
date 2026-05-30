"""
Neo4j client for graph database operations.
"""
from typing import List, Dict, Any, Optional, cast
from typing import LiteralString
from neo4j import GraphDatabase, Driver
import logging
import asyncio
from functools import partial

from src.core.config import settings

logger = logging.getLogger(__name__)

RHIZOME_NODE_LABELS = ["Entry", "Concept", "Goal", "Experiment", "Analysis", "Topic"]


def _rhizome_node_labels(node_types: Optional[List[str]]) -> List[str]:
    """Return list of node labels to query, optionally filtered by node_types."""
    if not node_types:
        return list(RHIZOME_NODE_LABELS)
    return [nt for nt in RHIZOME_NODE_LABELS if nt in node_types]


def _rhizome_time_filter(time_period: Optional[str]) -> str:
    """Return Cypher snippet for time filter on Entry nodes, or empty string."""
    if not time_period:
        return ""
    if time_period == "past":
        return "AND n.timestamp < datetime()"
    if time_period == "present":
        return "AND n.timestamp >= datetime() - duration({days: 30}) AND n.timestamp <= datetime()"
    if time_period == "future":
        return "AND n.timestamp > datetime()"
    return ""


def _node_description(node: Dict[str, Any], node_type: Optional[str]) -> str:
    """Build short description for a node by its type."""
    if node_type == "Entry":
        return (node.get("title") or node.get("content_summary") or node.get("content") or "")[:100]
    if node_type == "Concept":
        return node.get("description", node.get("name", ""))[:100]
    if node_type == "Goal":
        return node.get("description", node.get("title", ""))[:100]
    if node_type == "Experiment":
        return node.get("description", node.get("title", ""))[:100]
    if node_type == "Analysis":
        return node.get("summary", node.get("content", ""))[:100]
    return ""


def _node_to_graph_item(node: Dict[str, Any], node_id: str, user_id: str, node_type: Optional[str]) -> Dict[str, Any]:
    """Build a single node dict for graph response."""
    description = _node_description(node, node_type)
    
    props = {}
    for k, v in node.items():
        if k in ["id", "user_id"]:
            continue
        # Serialize database-specific date/time objects for Pydantic
        if hasattr(v, "iso_format"):
            props[k] = v.iso_format()
        elif hasattr(v, "isoformat"):
            props[k] = v.isoformat()
        else:
            props[k] = v
            
    return {
        "id": node_id,
        "user": user_id,
        "description": description,
        "type": node_type or "Unknown",
        **props
    }


class Neo4jClient:
    """Client for Neo4j graph database operations."""
    
    def __init__(self):
        """Initialize Neo4j driver."""
        self.driver: Optional[Driver] = None
        self._connected = False
    
    def _ensure_connected(self):
        """Ensure Neo4j driver is connected (lazy initialization)."""
        if not self._connected:
            self._connect()
    
    def _connect(self):
        """Create Neo4j driver connection."""
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            with self.driver.session() as session:
                session.run("RETURN 1")
            self._connected = True
            logger.info("Neo4j connection established")
            self._ensure_constraints()
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def _ensure_constraints(self):
        """Create unique constraints if they don't exist."""
        if not self.driver:
            return
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entry) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (g:Goal) REQUIRE g.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Experiment) REQUIRE e.id IS UNIQUE",
        ]
        try:
            with self.driver.session() as session:
                for c in constraints:
                    session.run(cast(LiteralString, c))
            logger.info("Neo4j unique constraints ensured")
        except Exception as e:
            logger.warning(f"Failed to create Neo4j constraints: {e}")
    
    def close(self):
        """Close Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        self._ensure_connected()
        
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")
        
        try:
            with self.driver.session() as session:
                result = session.run(cast(LiteralString, query), parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Neo4j query error: {e}")
            raise
    
    async def execute_query_async(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query asynchronously and return results."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(self.execute_query, query, parameters))

    def _append_source_node_if_new(
        self,
        record: Dict[str, Any],
        user_id: str,
        node_labels: List[str],
        node_ids: set[str],
        nodes: List[Dict[str, Any]],
    ) -> str:
        """Append source node from record if not already present and return node_id."""
        node = dict(record["n"])
        n_labels = record.get("n_labels", [])
        node_id = str(record.get("n_id", "") or node.get("id", ""))
        if node_id and node_id not in node_ids:
            node_ids.add(node_id)
            node_type = next((lbl for lbl in node_labels if lbl in n_labels), None)
            nodes.append(_node_to_graph_item(node, node_id, user_id, node_type))
        return node_id

    def _append_target_node_if_new(
        self,
        rel: Dict[str, Any],
        target_id: str,
        user_id: str,
        node_ids: set[str],
        nodes: List[Dict[str, Any]],
    ) -> None:
        """Append target node from relationship payload if not already present."""
        if target_id in node_ids or not rel.get("m_node"):
            return
        m_node = rel["m_node"]
        m_labels = rel.get("m_labels", [])
        m_type = next((lbl for lbl in RHIZOME_NODE_LABELS if lbl in m_labels), m_labels[0] if m_labels else "Unknown")
        node_ids.add(target_id)
        nodes.append(_node_to_graph_item(dict(m_node), target_id, user_id, m_type))

    def _append_relationship_link(
        self,
        rel: Dict[str, Any],
        source_id: str,
        links: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Append relationship as graph link and return target_id when valid."""
        if not rel or not rel.get("target"):
            return None
        target_id = str(rel["target"])
        rel_props = rel.get("rel_props") or {}
        links.append({
            "source": source_id,
            "target": target_id,
            "type": rel.get("type", "RELATED"),
            "reason": rel_props.get("reason") or rel_props.get("justification") or rel_props.get("description") or "",
        })
        return target_id
    
    async def get_rhizome_graph(
        self, 
        user_id: str,
        node_types: Optional[List[str]] = None,
        time_period: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get the complete graph for a user in format suitable for react-force-graph.
        """
        node_labels = _rhizome_node_labels(node_types)
        
        # Строим условия выборки через OR, чтобы поддерживать серверы с Neo4j 4.x
        if node_labels:
            label_cond_n = " OR ".join([f"n:{lbl}" for lbl in node_labels])
        else:
            label_cond_n = "FALSE"
            
        time_filter = _rhizome_time_filter(time_period)
        
        query = f"""
        MATCH (n)
        WHERE ({label_cond_n}) AND n.user_id = $user_id {time_filter}
        OPTIONAL MATCH (n)-[r]->(m)
        WITH n, labels(n) as n_labels,
             collect(CASE WHEN r IS NOT NULL AND m IS NOT NULL THEN {{
               target: CASE WHEN m.id IS NOT NULL THEN toString(m.id) ELSE coalesce(m.name, m.title, toString(id(m))) END,
               type: type(r),
               m_labels: labels(m),
               m_node: m,
               rel_props: properties(r)
             }} ELSE null END) as raw_rels
        WITH n, n_labels,
             [x IN raw_rels WHERE x IS NOT NULL] as relationships
        RETURN n, n_labels, relationships,
               CASE WHEN n.id IS NOT NULL THEN toString(n.id) ELSE coalesce(n.name, n.title, toString(id(n))) END as n_id
        """
        
        results = await self.execute_query_async(query, {"user_id": user_id})
        nodes = []
        links = []
        node_ids = set()
        
        for record in results:
            node_id = self._append_source_node_if_new(record, user_id, node_labels, node_ids, nodes)
            relationships = record.get("relationships", [])
            for rel in relationships:
                target_id = self._append_relationship_link(rel, node_id, links)
                if not target_id:
                    continue
                # Add target node if not already present (e.g. Topic nodes)
                self._append_target_node_if_new(rel, target_id, user_id, node_ids, nodes)

        logger.info(
            "get_rhizome_graph: user=%s nodes=%d links=%d sample_rels=%s",
            user_id, len(nodes), len(links),
            [r.get("relationships") for r in results[:3]] if results else []
        )
        return {"nodes": nodes, "links": links}
    
    async def search_nodes(self, user_id: str, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search nodes by title, name or content (case-insensitive)."""
        q = query.strip().lower()
        search_query = """
        MATCH (n)
        WHERE n.user_id = $user_id
        AND (
            (n:Entry AND (
                toLower(coalesce(n.title, '')) CONTAINS $query
                OR toLower(coalesce(n.content, '')) CONTAINS $query
                OR toLower(coalesce(n.content_summary, '')) CONTAINS $query
            ))
            OR (n:Concept AND toLower(coalesce(n.name, '')) CONTAINS $query)
            OR (n:Goal AND (
                toLower(coalesce(n.title, '')) CONTAINS $query
                OR toLower(coalesce(n.description, '')) CONTAINS $query
            ))
            OR (n:Experiment AND (
                toLower(coalesce(n.title, '')) CONTAINS $query
                OR toLower(coalesce(n.description, '')) CONTAINS $query
            ))
            OR (n:Analysis AND (
                toLower(coalesce(n.title, '')) CONTAINS $query
                OR toLower(coalesce(n.content, '')) CONTAINS $query
            ))
        )
        RETURN n, labels(n) as n_labels
        LIMIT $limit
        """
        
        results = await self.execute_query_async(search_query, {
            "user_id": user_id,
            "query": q,
            "limit": limit
        })
        
        nodes = []
        for record in results:
            node = record["n"]
            n_labels = record.get("n_labels", [])
            node_id = str(node.get("id", ""))
            node_type = next((lbl for lbl in RHIZOME_NODE_LABELS if lbl in n_labels), None)
            nodes.append(_node_to_graph_item(node, node_id, user_id, node_type))
        return nodes
    
    async def get_node_by_id(self, node_id: str, node_type: str) -> Optional[Dict[str, Any]]:
        """Get a single node by ID and type."""
        query = f"""
        MATCH (n:{node_type} {{id: $node_id}})
        RETURN n
        LIMIT 1
        """
        
        results = await self.execute_query_async(query, {"node_id": node_id})
        if results:
            node = results[0]["n"]
            return dict(node)
        return None
    
    async def get_related_nodes(
        self, 
        node_id: str, 
        relationship_type: str,
        target_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get nodes related to a given node via a specific relationship."""
        rel_filter = f":{relationship_type}" if relationship_type else ""
        target_filter = f":{target_type}" if target_type else ""
        
        query = f"""
        MATCH (n {{id: $node_id}})-[r{rel_filter}]->(m{target_filter})
        RETURN m
        """
        
        results = await self.execute_query_async(query, {"node_id": node_id})
        return [dict(record["m"]) for record in results]

    async def get_entry_graph_relations(
        self,
        entry_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """Bidirectional RELATES_TO links between this entry and other entries or goals."""
        query = """
        MATCH (e:Entry {id: $entry_id, user_id: $user_id})-[r:RELATES_TO]-(other)
        WHERE other.user_id = $user_id AND other.id <> $entry_id
          AND (other:Entry OR other:Goal)
        RETURN other, labels(other) AS other_labels, properties(r) AS rel_props
        ORDER BY coalesce(rel_props.score, 0) DESC
        """
        results = await self.execute_query_async(
            query, {"entry_id": entry_id, "user_id": user_id},
        )
        relations: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for record in results:
            other = dict(record["other"])
            other_id = str(other.get("id", ""))
            if not other_id or other_id in seen:
                continue
            seen.add(other_id)
            rel_props = record.get("rel_props") or {}
            other_labels = record.get("other_labels") or []
            is_goal = "Goal" in other_labels
            title = (other.get("title") or "").strip()
            if is_goal:
                content = (other.get("description") or "").strip()
                entity_type = "goal"
            else:
                content = (other.get("content") or "").strip()
                entity_type = "observation"
            relations.append({
                "id": other_id,
                "entity_type": entity_type,
                "title": title or content[:120] or ("Цель" if is_goal else "Наблюдение"),
                "description": content[:300] if content else None,
                "relation_type": "RELATES_TO",
                "score": rel_props.get("score"),
                "reason": rel_props.get("reason"),
            })
        return relations

    async def get_entries_documenting_experiment(self, experiment_id: str) -> List[Dict[str, Any]]:
        """Entry -[:DOCUMENTS]-> Experiment: записи, документирующие эксперимент."""
        query = """
        MATCH (e:Entry)-[:DOCUMENTS]->(exp:Experiment {id: $experiment_id})
        RETURN e
        """
        results = await self.execute_query_async(query, {"experiment_id": experiment_id})
        return [dict(record["e"]) for record in results]

    async def update_experiment_node(
        self,
        experiment_id: str,
        user_id: str,
        status: Optional[str] = None,
        success: Optional[int] = None,
        outcome: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Обновить поля узла Experiment (только переданные)."""
        query = """
        MATCH (exp:Experiment {id: $experiment_id, user_id: $user_id})
        SET exp.updated_at = datetime()
        """
        params: Dict[str, Any] = {"experiment_id": experiment_id, "user_id": user_id}
        if status is not None:
            query += ", exp.status = $status"
            params["status"] = status
        if success is not None:
            query += ", exp.success = $success"
            params["success"] = success
        if outcome is not None:
            query += ", exp.outcome = $outcome"
            params["outcome"] = outcome
        query += "\nRETURN exp"
        results = await self.execute_query_async(query, params)
        if results:
            return dict(results[0]["exp"])
        return None


# Singleton instance
neo4j_client = Neo4jClient()
