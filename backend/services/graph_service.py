"""Business logic for nodes, connections and full auditing."""

from __future__ import annotations

from typing import TypeVar, cast
import json
import sqlite3
import uuid

from backend.repository import SQLiteRepository
from core.visualization import build_vis_payload
from datamodels.graph_models import (
    AuditAction,
    AuditExportResult,
    AuditIntegrityReport,
    AuditLog,
    AuditQuery,
    AuditRecord,
    Connection,
    ConnectionCreatePayload,
    ConnectionType,
    ConnectionUpdatePayload,
    DeletePayload,
    EntityType,
    GraphClearPayload,
    GraphClearResult,
    GraphDeletePayload,
    GraphDeleteResult,
    GraphExportResult,
    GraphImportPayload,
    GraphImportResult,
    GraphLoadPayload,
    GraphLoadResult,
    GraphSavePayload,
    GraphSaveResult,
    GraphSnapshot,
    Node,
    NodeCreatePayload,
    NodeUpdatePayload,
    Position,
    SavedGraphSummary,
    SubgraphQueryPayload,
    SubgraphResult,
    utc_now,
)


T = TypeVar("T")


def _safe_json_loads(raw: str | None, default: T) -> T:
    if not raw:
        return default
    try:
        return cast(T, json.loads(raw))
    except json.JSONDecodeError:
        return default


class GraphService:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    @staticmethod
    def _owner(owner_id: str) -> str:
        normalized = owner_id.strip()
        if not normalized:
            raise ValueError("owner_id is required.")
        return normalized

    def list_nodes(self, owner_id: str, include_deleted: bool = False) -> list[Node]:
        normalized_owner = self._owner(owner_id)
        query = "SELECT * FROM nodes WHERE owner_id = ?"
        params: list[object] = [normalized_owner]
        if not include_deleted:
            query += " AND is_deleted = 0"
        query += " ORDER BY created_at ASC"
        rows = self.repository.fetch_all(query, params)
        return [self._row_to_node(row) for row in rows]

    def get_node(self, owner_id: str, node_id: str) -> Node | None:
        normalized_owner = self._owner(owner_id)
        row = self.repository.fetch_one(
            "SELECT * FROM nodes WHERE owner_id = ? AND id = ? AND is_deleted = 0",
            (normalized_owner, node_id),
        )
        if not row:
            return None
        return self._row_to_node(row)

    def create_node(
        self,
        owner_id: str,
        payload: NodeCreatePayload,
        actor: str,
        reason: str | None = None,
    ) -> Node:
        normalized_owner = self._owner(owner_id)
        content = payload.content.strip()
        if not content:
            raise ValueError("`content` is required.")

        node = Node(
            content=content,
            summary=payload.summary.strip(),
            position=Position(
                x=float(payload.position.x),
                y=float(payload.position.y),
            ),
            color=(payload.color.strip() or "#157f83"),
            size=max(float(payload.size), 0.2),
            tags=[str(item) for item in payload.tags],
            confidence=self._clamp(float(payload.confidence), 0.0, 1.0),
            evidence=[str(item) for item in payload.evidence],
        )

        audit_reason = reason if reason is not None else payload.reason

        with self.repository.transaction() as conn:
            conn.execute(
                """
                INSERT INTO nodes (
                    id, owner_id, content, summary,
                    position_x, position_y,
                    color, size, tags,
                    confidence, evidence,
                    created_at, updated_at,
                    version, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
                    normalized_owner,
                    node.content,
                    node.summary,
                    node.position.x,
                    node.position.y,
                    node.color,
                    node.size,
                    json.dumps(node.tags, ensure_ascii=False),
                    node.confidence,
                    json.dumps(node.evidence, ensure_ascii=False),
                    node.created_at,
                    node.updated_at,
                    node.version,
                    int(node.is_deleted),
                ),
            )
            self._insert_audit(
                conn,
                normalized_owner,
                AuditLog(
                    entity_type=EntityType.NODE.value,
                    entity_id=node.id,
                    action=AuditAction.CREATE.value,
                    actor=actor,
                    reason=audit_reason,
                    after_state=node.to_state(),
                ),
            )

        return node

    def update_node(
        self,
        owner_id: str,
        node_id: str,
        payload: NodeUpdatePayload,
        actor: str,
        reason: str | None = None,
    ) -> Node | None:
        normalized_owner = self._owner(owner_id)
        row = self.repository.fetch_one(
            "SELECT * FROM nodes WHERE owner_id = ? AND id = ?",
            (normalized_owner, node_id),
        )
        if not row:
            return None

        current = self._row_to_node(row)
        if current.is_deleted:
            return None

        before_state = current.to_state()
        updated = Node.from_state(before_state)

        if payload.has("content"):
            if not payload.content:
                raise ValueError("`content` cannot be empty.")
            updated.content = payload.content
        if payload.has("summary") and payload.summary is not None:
            updated.summary = payload.summary
        if payload.has("color") and payload.color is not None:
            updated.color = payload.color
        if payload.has("size") and payload.size is not None:
            updated.size = max(float(payload.size), 0.2)
        if payload.has("confidence") and payload.confidence is not None:
            updated.confidence = self._clamp(float(payload.confidence), 0.0, 1.0)
        if payload.has("tags") and payload.tags is not None:
            updated.tags = [str(item) for item in payload.tags]
        if payload.has("evidence") and payload.evidence is not None:
            updated.evidence = [str(item) for item in payload.evidence]
        if payload.has("position") and payload.position is not None:
            updated.position = Position(
                x=float(payload.position.x),
                y=float(payload.position.y),
            )

        updated.version = current.version + 1
        updated.updated_at = utc_now()
        after_state = updated.to_state()

        audit_reason = reason if reason is not None else payload.reason

        with self.repository.transaction() as conn:
            conn.execute(
                """
                UPDATE nodes
                SET
                    content = ?,
                    summary = ?,
                    position_x = ?,
                    position_y = ?,
                    color = ?,
                    size = ?,
                    tags = ?,
                    confidence = ?,
                    evidence = ?,
                    updated_at = ?,
                    version = ?
                WHERE owner_id = ? AND id = ?
                """,
                (
                    updated.content,
                    updated.summary,
                    updated.position.x,
                    updated.position.y,
                    updated.color,
                    updated.size,
                    json.dumps(updated.tags, ensure_ascii=False),
                    updated.confidence,
                    json.dumps(updated.evidence, ensure_ascii=False),
                    updated.updated_at,
                    updated.version,
                    normalized_owner,
                    node_id,
                ),
            )
            self._insert_audit(
                conn,
                normalized_owner,
                AuditLog(
                    entity_type=EntityType.NODE.value,
                    entity_id=node_id,
                    action=AuditAction.UPDATE.value,
                    actor=actor,
                    reason=audit_reason,
                    before_state=before_state,
                    after_state=after_state,
                ),
            )

        return updated

    def delete_node(
        self,
        owner_id: str,
        node_id: str,
        actor: str,
        payload: DeletePayload | None = None,
        reason: str | None = None,
    ) -> bool:
        normalized_owner = self._owner(owner_id)
        row = self.repository.fetch_one(
            "SELECT * FROM nodes WHERE owner_id = ? AND id = ?",
            (normalized_owner, node_id),
        )
        if not row:
            return False

        node = self._row_to_node(row)
        if node.is_deleted:
            return False

        before_state = node.to_state()
        node.is_deleted = True
        node.version += 1
        node.updated_at = utc_now()
        after_state = node.to_state()

        payload_reason = payload.reason if payload else None
        audit_reason = reason if reason is not None else payload_reason

        with self.repository.transaction() as conn:
            conn.execute(
                """
                UPDATE nodes
                SET is_deleted = 1, version = ?, updated_at = ?
                WHERE owner_id = ? AND id = ?
                """,
                (node.version, node.updated_at, normalized_owner, node_id),
            )
            self._insert_audit(
                conn,
                normalized_owner,
                AuditLog(
                    entity_type=EntityType.NODE.value,
                    entity_id=node_id,
                    action=AuditAction.DELETE.value,
                    actor=actor,
                    reason=audit_reason,
                    before_state=before_state,
                    after_state=after_state,
                ),
            )

            connected_rows = conn.execute(
                """
                SELECT * FROM connections
                WHERE owner_id = ? AND is_deleted = 0 AND (source_id = ? OR target_id = ?)
                """,
                (normalized_owner, node_id, node_id),
            ).fetchall()
            for edge_row in connected_rows:
                edge = self._row_to_connection(edge_row)
                edge_before = edge.to_state()
                edge.is_deleted = True
                edge.version += 1
                edge.updated_at = utc_now()

                conn.execute(
                    """
                    UPDATE connections
                    SET is_deleted = 1, version = ?, updated_at = ?
                    WHERE owner_id = ? AND id = ?
                    """,
                    (edge.version, edge.updated_at, normalized_owner, edge.id),
                )
                cascade_reason = (audit_reason or "") + " [cascade by node deletion]"
                self._insert_audit(
                    conn,
                    normalized_owner,
                    AuditLog(
                        entity_type=EntityType.CONNECTION.value,
                        entity_id=edge.id,
                        action=AuditAction.DELETE.value,
                        actor=actor,
                        reason=cascade_reason,
                        before_state=edge_before,
                        after_state=edge.to_state(),
                    ),
                )

        return True

    def list_connections(self, owner_id: str, include_deleted: bool = False) -> list[Connection]:
        normalized_owner = self._owner(owner_id)
        query = "SELECT * FROM connections WHERE owner_id = ?"
        params: list[object] = [normalized_owner]
        if not include_deleted:
            query += " AND is_deleted = 0"
        query += " ORDER BY created_at ASC"
        rows = self.repository.fetch_all(query, params)
        return [self._row_to_connection(row) for row in rows]

    def create_connection(
        self,
        owner_id: str,
        payload: ConnectionCreatePayload,
        actor: str,
        reason: str | None = None,
    ) -> Connection:
        normalized_owner = self._owner(owner_id)
        source_id = payload.source_id
        target_id = payload.target_id
        if not source_id or not target_id:
            raise ValueError("`source_id` and `target_id` are required.")
        if source_id == target_id:
            raise ValueError("Self-loop is not allowed for connection.")

        conn_type_raw = payload.conn_type
        if conn_type_raw not in ConnectionType.values():
            raise ValueError("Invalid `conn_type`.")

        source = self.repository.fetch_one(
            "SELECT id FROM nodes WHERE owner_id = ? AND id = ? AND is_deleted = 0",
            (normalized_owner, source_id),
        )
        target = self.repository.fetch_one(
            "SELECT id FROM nodes WHERE owner_id = ? AND id = ? AND is_deleted = 0",
            (normalized_owner, target_id),
        )
        if not source or not target:
            raise ValueError("Source/target node does not exist or is deleted.")

        edge = Connection(
            source_id=source_id,
            target_id=target_id,
            conn_type=conn_type_raw,
            description=payload.description,
            strength=max(float(payload.strength), 0.1),
        )

        audit_reason = reason if reason is not None else payload.reason

        with self.repository.transaction() as conn:
            conn.execute(
                """
                INSERT INTO connections (
                    id, owner_id, source_id, target_id,
                    conn_type, description, strength,
                    created_at, updated_at,
                    version, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    normalized_owner,
                    edge.source_id,
                    edge.target_id,
                    edge.conn_type,
                    edge.description,
                    edge.strength,
                    edge.created_at,
                    edge.updated_at,
                    edge.version,
                    int(edge.is_deleted),
                ),
            )
            self._insert_audit(
                conn,
                normalized_owner,
                AuditLog(
                    entity_type=EntityType.CONNECTION.value,
                    entity_id=edge.id,
                    action=AuditAction.CREATE.value,
                    actor=actor,
                    reason=audit_reason,
                    after_state=edge.to_state(),
                ),
            )

        return edge

    def update_connection(
        self,
        owner_id: str,
        conn_id: str,
        payload: ConnectionUpdatePayload,
        actor: str,
        reason: str | None = None,
    ) -> Connection | None:
        normalized_owner = self._owner(owner_id)
        row = self.repository.fetch_one(
            "SELECT * FROM connections WHERE owner_id = ? AND id = ?",
            (normalized_owner, conn_id),
        )
        if not row:
            return None

        edge = self._row_to_connection(row)
        if edge.is_deleted:
            return None

        before_state = edge.to_state()
        updated = Connection.from_state(before_state)

        if payload.has("description") and payload.description is not None:
            updated.description = payload.description
        if payload.has("strength") and payload.strength is not None:
            updated.strength = max(float(payload.strength), 0.1)
        if payload.has("conn_type") and payload.conn_type is not None:
            if payload.conn_type not in ConnectionType.values():
                raise ValueError("Invalid `conn_type`.")
            updated.conn_type = payload.conn_type

        updated.version = edge.version + 1
        updated.updated_at = utc_now()
        after_state = updated.to_state()

        audit_reason = reason if reason is not None else payload.reason

        with self.repository.transaction() as conn:
            conn.execute(
                """
                UPDATE connections
                SET
                    conn_type = ?,
                    description = ?,
                    strength = ?,
                    updated_at = ?,
                    version = ?
                WHERE owner_id = ? AND id = ?
                """,
                (
                    updated.conn_type,
                    updated.description,
                    updated.strength,
                    updated.updated_at,
                    updated.version,
                    normalized_owner,
                    conn_id,
                ),
            )
            self._insert_audit(
                conn,
                normalized_owner,
                AuditLog(
                    entity_type=EntityType.CONNECTION.value,
                    entity_id=conn_id,
                    action=AuditAction.UPDATE.value,
                    actor=actor,
                    reason=audit_reason,
                    before_state=before_state,
                    after_state=after_state,
                ),
            )

        return updated

    def delete_connection(
        self,
        owner_id: str,
        conn_id: str,
        actor: str,
        payload: DeletePayload | None = None,
        reason: str | None = None,
    ) -> bool:
        normalized_owner = self._owner(owner_id)
        row = self.repository.fetch_one(
            "SELECT * FROM connections WHERE owner_id = ? AND id = ?",
            (normalized_owner, conn_id),
        )
        if not row:
            return False

        edge = self._row_to_connection(row)
        if edge.is_deleted:
            return False

        before_state = edge.to_state()
        edge.is_deleted = True
        edge.version += 1
        edge.updated_at = utc_now()

        payload_reason = payload.reason if payload else None
        audit_reason = reason if reason is not None else payload_reason

        with self.repository.transaction() as conn:
            conn.execute(
                """
                UPDATE connections
                SET is_deleted = 1, version = ?, updated_at = ?
                WHERE owner_id = ? AND id = ?
                """,
                (edge.version, edge.updated_at, normalized_owner, conn_id),
            )
            self._insert_audit(
                conn,
                normalized_owner,
                AuditLog(
                    entity_type=EntityType.CONNECTION.value,
                    entity_id=conn_id,
                    action=AuditAction.DELETE.value,
                    actor=actor,
                    reason=audit_reason,
                    before_state=before_state,
                    after_state=edge.to_state(),
                ),
            )

        return True

    def graph_snapshot(self, owner_id: str) -> GraphSnapshot:
        normalized_owner = self._owner(owner_id)
        node_rows = self.repository.fetch_all(
            "SELECT * FROM nodes WHERE owner_id = ? AND is_deleted = 0 ORDER BY created_at ASC",
            (normalized_owner,),
        )
        conn_rows = self.repository.fetch_all(
            "SELECT * FROM connections WHERE owner_id = ? AND is_deleted = 0 ORDER BY created_at ASC",
            (normalized_owner,),
        )

        nodes = [self._row_to_node(row) for row in node_rows]
        connections = [self._row_to_connection(row) for row in conn_rows]
        vis_payload = build_vis_payload(nodes, connections)

        return GraphSnapshot(
            nodes=nodes,
            connections=connections,
            visualization=vis_payload,
        )

    def query_subgraph(self, owner_id: str, payload: SubgraphQueryPayload) -> SubgraphResult:
        """Query a subgraph based on various criteria."""
        normalized_owner = self._owner(owner_id)
        
        # Get full active graph
        snapshot = self.graph_snapshot(normalized_owner)
        all_nodes = snapshot.nodes
        all_connections = snapshot.connections
        
        total_nodes = len(all_nodes)
        total_connections = len(all_connections)
        
        # If graph is empty, return empty result
        if not all_nodes:
            vis_payload = build_vis_payload([], []) if payload.include_visualization else build_vis_payload([], [])
            return SubgraphResult(
                query=payload,
                snapshot=GraphSnapshot(nodes=[], connections=[], visualization=vis_payload),
                total_nodes_in_graph=total_nodes,
                total_connections_in_graph=total_connections,
                selected_node_count=0,
                selected_connection_count=0,
                seed_node_count=0,
                message="Empty graph"
            )
        
        # Score all nodes
        node_scores = []
        for node in all_nodes:
            score = self._score_node_for_subgraph(node, payload)
            node_scores.append((node, score))
        
        # Select initial seed nodes based on scores
        seed_nodes = self._select_initial_seeds(node_scores, payload)
        seed_node_ids = {node.id for node in seed_nodes}
        
        # Expand neighborhood
        expanded_node_ids = self._expand_subgraph_nodes(
            seed_node_ids, all_connections, payload.max_hops, payload.conn_types
        )
        
        # Filter by confidence (but keep seeds even if below threshold)
        filtered_node_ids = set()
        for node_id in expanded_node_ids:
            node = next((n for n in all_nodes if n.id == node_id), None)
            if node:
                # Keep seed nodes even if below confidence threshold
                if node.confidence >= payload.min_confidence or node_id in seed_node_ids:
                    filtered_node_ids.add(node_id)
        
        # Get selected nodes
        selected_nodes = [n for n in all_nodes if n.id in filtered_node_ids]
        
        # Trim to max_nodes
        selected_nodes = self._trim_subgraph_nodes(selected_nodes, seed_node_ids, payload.max_nodes)
        final_node_ids = {n.id for n in selected_nodes}
        
        # Select connections between selected nodes
        selected_connections = self._select_subgraph_connections(
            all_connections, final_node_ids, payload.conn_types, payload.max_connections
        )
        
        # Remove orphans if requested
        if not payload.include_orphans:
            connected_node_ids = set()
            for conn in selected_connections:
                connected_node_ids.add(conn.source_id)
                connected_node_ids.add(conn.target_id)
            
            non_orphan_nodes = []
            for node in selected_nodes:
                if node.id in connected_node_ids or node.id in seed_node_ids:
                    non_orphan_nodes.append(node)
            selected_nodes = non_orphan_nodes
            final_node_ids = {n.id for n in selected_nodes}
            
            # Re-filter connections after removing orphans
            selected_connections = self._select_subgraph_connections(
                all_connections, final_node_ids, payload.conn_types, payload.max_connections
            )
        
        # Build visualization
        vis_payload = build_vis_payload(selected_nodes, selected_connections) if payload.include_visualization else build_vis_payload([], [])
        
        return SubgraphResult(
            query=payload,
            snapshot=GraphSnapshot(
                nodes=selected_nodes,
                connections=selected_connections,
                visualization=vis_payload
            ),
            total_nodes_in_graph=total_nodes,
            total_connections_in_graph=total_connections,
            selected_node_count=len(selected_nodes),
            selected_connection_count=len(selected_connections),
            seed_node_count=len(seed_node_ids & final_node_ids),
            message=f"Selected {len(selected_nodes)} nodes and {len(selected_connections)} connections"
        )

    def _normalize_query_text(self, text: str | None) -> str:
        """Normalize query text for matching."""
        if not text:
            return ""
        return text.lower().strip()

    def _tokenize_query(self, query: str) -> list[str]:
        """Tokenize query text into words (simple split on non-alphanumeric)."""
        import re
        # Split on non-alphanumeric characters
        tokens = re.findall(r'[a-z0-9]+', query.lower())
        return tokens

    def _score_node_for_subgraph(self, node: Node, payload: SubgraphQueryPayload) -> float:
        """Score a node based on query relevance and other factors."""
        score = 0.0
        
        # Query lexical matching
        if payload.query:
            normalized_query = self._normalize_query_text(payload.query)
            tokens = self._tokenize_query(normalized_query)
            
            # Match against content
            content_lower = node.content.lower()
            summary_lower = node.summary.lower()
            
            # For English tokens, check word overlap
            for token in tokens:
                if token in content_lower:
                    score += 2.0
                if token in summary_lower:
                    score += 1.5
            
            # For Chinese or general substring matching
            if normalized_query and len(normalized_query) > 1:
                if normalized_query in content_lower:
                    score += 5.0
                if normalized_query in summary_lower:
                    score += 3.0
        
        # Seed node bonus (high weight)
        if node.id in payload.seed_node_ids:
            score += 50.0
        
        # Tag matching
        if payload.tags:
            node_tags_lower = [t.lower() for t in node.tags]
            for tag in payload.tags:
                if tag.lower() in node_tags_lower:
                    score += 10.0
        
        # Evidence keyword matching
        if payload.evidence_keywords:
            evidence_text = ' '.join(node.evidence).lower()
            for keyword in payload.evidence_keywords:
                if keyword.lower() in evidence_text:
                    score += 8.0
        
        # Confidence bonus (light weight, don't dominate)
        score += node.confidence * 2.0
        
        # Recency bonus (very light weight) - using updated_at as proxy
        # This is a simple implementation; could be enhanced with actual date parsing
        try:
            # Just use version as a simple recency proxy
            score += min(node.version * 0.1, 1.0)
        except Exception:
            pass
        
        return score

    def _select_initial_seeds(
        self, 
        node_scores: list[tuple[Node, float]], 
        payload: SubgraphQueryPayload
    ) -> list[Node]:
        """Select initial seed nodes based on scores."""
        # Sort by score descending, then by created_at for stability
        sorted_nodes = sorted(
            node_scores,
            key=lambda x: (-x[1], x[0].created_at, x[0].id)
        )
        
        # Filter out zero-score nodes unless they are explicit seeds
        candidates = []
        for node, score in sorted_nodes:
            if score > 0 or node.id in payload.seed_node_ids:
                candidates.append(node)
        
        # If no query/seed/tags/evidence provided, return recent nodes
        has_criteria = (
            payload.query or 
            payload.seed_node_ids or 
            payload.tags or 
            payload.evidence_keywords
        )
        
        if not has_criteria:
            # Return up to max_nodes most recently created nodes
            recent_nodes = sorted(
                [node for node, _ in node_scores],
                key=lambda n: n.created_at,
                reverse=True
            )[:payload.max_nodes]
            return recent_nodes
        
        return candidates[:payload.max_nodes]

    def _build_active_adjacency(
        self, 
        connections: list[Connection],
        allowed_conn_types: list[str] | None = None
    ) -> dict[str, list[tuple[str, Connection]]]:
        """Build adjacency list from connections."""
        adj: dict[str, list[tuple[str, Connection]]] = {}
        
        for conn in connections:
            # Filter by connection types if specified
            if allowed_conn_types and conn.conn_type not in allowed_conn_types:
                continue
            
            if conn.source_id not in adj:
                adj[conn.source_id] = []
            if conn.target_id not in adj:
                adj[conn.target_id] = []
            
            # Bidirectional
            adj[conn.source_id].append((conn.target_id, conn))
            adj[conn.target_id].append((conn.source_id, conn))
        
        return adj

    def _expand_subgraph_nodes(
        self,
        seed_node_ids: set[str],
        all_connections: list[Connection],
        max_hops: int,
        allowed_conn_types: list[str] | None = None
    ) -> set[str]:
        """Expand from seed nodes using BFS up to max_hops."""
        if max_hops == 0:
            return seed_node_ids.copy()
        
        # Build adjacency with optional type filtering
        adj = self._build_active_adjacency(all_connections, allowed_conn_types if allowed_conn_types else None)
        
        # BFS expansion
        visited = seed_node_ids.copy()
        current_level = seed_node_ids.copy()
        
        for hop in range(max_hops):
            next_level = set()
            for node_id in current_level:
                neighbors = adj.get(node_id, [])
                for neighbor_id, conn in neighbors:
                    if neighbor_id not in visited:
                        # Prioritize high-priority edge types
                        if self._is_high_priority_edge(conn.conn_type):
                            next_level.add(neighbor_id)
                        else:
                            # Add lower priority edges but process them later
                            next_level.add(neighbor_id)
            
            visited.update(next_level)
            current_level = next_level
            
            if not current_level:
                break
        
        return visited

    def _is_high_priority_edge(self, conn_type: str) -> bool:
        """Check if connection type is high priority."""
        return conn_type in {"supports", "opposes", "leads_to"}

    def _select_subgraph_connections(
        self,
        all_connections: list[Connection],
        selected_node_ids: set[str],
        allowed_conn_types: list[str] | None = None,
        max_connections: int = 24
    ) -> list[Connection]:
        """Select connections between selected nodes."""
        candidates = []
        
        for conn in all_connections:
            # Both endpoints must be in selected nodes
            if conn.source_id not in selected_node_ids or conn.target_id not in selected_node_ids:
                continue
            
            # Filter by connection types if specified
            if allowed_conn_types and conn.conn_type not in allowed_conn_types:
                continue
            
            candidates.append(conn)
        
        # Sort by priority: high-priority types first, then by strength
        priority_order = {"supports": 0, "opposes": 1, "leads_to": 2, "derives_from": 3, "relates": 4}
        
        candidates.sort(
            key=lambda c: (
                priority_order.get(c.conn_type, 5),
                -c.strength,
                c.created_at,
                c.id
            )
        )
        
        return candidates[:max_connections]

    def _trim_subgraph_nodes(
        self,
        selected_nodes: list[Node],
        seed_node_ids: set[str],
        max_nodes: int
    ) -> list[Node]:
        """Trim selected nodes to max_nodes limit."""
        if len(selected_nodes) <= max_nodes:
            return selected_nodes
        
        # Priority: seeds first, then by score (already scored), then proximity
        # Since we don't have distance info here, just use creation order as tiebreaker
        nodes_with_priority = []
        for node in selected_nodes:
            is_seed = 0 if node.id in seed_node_ids else 1
            nodes_with_priority.append((is_seed, node.created_at, node.id, node))
        
        nodes_with_priority.sort(key=lambda x: (x[0], x[1], x[2]))
        
        return [item[3] for item in nodes_with_priority[:max_nodes]]

    def export_graph(self, owner_id: str) -> GraphExportResult:
        snapshot = self.graph_snapshot(owner_id)
        node_states = [node.to_state() for node in snapshot.nodes]
        connection_states = [conn.to_state() for conn in snapshot.connections]
        exported_at = utc_now()
        safe_stamp = (
            exported_at.replace(":", "-")
            .replace(".", "-")
            .replace("+", "p")
        )
        file_name = f"thinking-graph-export-{safe_stamp}.json"

        return GraphExportResult(
            format="thinking-graph-export-v1",
            exported_at=exported_at,
            node_count=len(node_states),
            connection_count=len(connection_states),
            suggested_file_name=file_name,
            nodes=node_states,
            connections=connection_states,
        )

    def save_graph(
        self,
        owner_id: str,
        payload: GraphSavePayload,
        actor: str,
        reason: str | None = None,
    ) -> GraphSaveResult:
        normalized_owner = self._owner(owner_id)
        name = self._normalize_snapshot_name(payload.name)
        saved_at = utc_now()
        snapshot = self.graph_snapshot(normalized_owner)
        node_states = [node.to_state() for node in snapshot.nodes]
        connection_states = [conn.to_state() for conn in snapshot.connections]
        snapshot_payload = {
            "name": name,
            "saved_at": saved_at,
            "reason": reason if reason is not None else payload.reason,
            "nodes": node_states,
            "connections": connection_states,
        }

        with self.repository.transaction() as conn:
            conn.execute(
                """
                INSERT INTO graph_snapshots (
                    owner_id, name, payload, node_count, connection_count, actor, saved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner_id, name) DO UPDATE SET
                    payload = excluded.payload,
                    node_count = excluded.node_count,
                    connection_count = excluded.connection_count,
                    actor = excluded.actor,
                    saved_at = excluded.saved_at
                """,
                (
                    normalized_owner,
                    name,
                    json.dumps(snapshot_payload, ensure_ascii=False),
                    len(node_states),
                    len(connection_states),
                    actor,
                    saved_at,
                ),
            )

        return GraphSaveResult(
            name=name,
            node_count=len(node_states),
            connection_count=len(connection_states),
            actor=actor,
            saved_at=saved_at,
            message="graph snapshot saved",
        )

    def list_saved_graphs(self, owner_id: str) -> list[SavedGraphSummary]:
        normalized_owner = self._owner(owner_id)
        rows = self.repository.fetch_all(
            """
            SELECT name, node_count, connection_count, actor, saved_at
            FROM graph_snapshots
            WHERE owner_id = ?
            ORDER BY saved_at DESC
            """,
            (normalized_owner,),
        )
        return [
            SavedGraphSummary(
                name=str(row["name"]),
                node_count=int(row["node_count"]),
                connection_count=int(row["connection_count"]),
                actor=str(row["actor"]),
                saved_at=str(row["saved_at"]),
            )
            for row in rows
        ]

    def load_graph(
        self,
        owner_id: str,
        payload: GraphLoadPayload,
        actor: str,
        reason: str | None = None,
    ) -> GraphLoadResult:
        normalized_owner = self._owner(owner_id)
        name = self._normalize_snapshot_name(payload.name)
        row = self.repository.fetch_one(
            "SELECT payload FROM graph_snapshots WHERE owner_id = ? AND name = ?",
            (normalized_owner, name),
        )
        if not row:
            raise ValueError("saved graph not found")

        snapshot_data = _safe_json_loads(row["payload"], {})
        raw_nodes = snapshot_data.get("nodes", []) if isinstance(snapshot_data, dict) else []
        raw_connections = (
            snapshot_data.get("connections", []) if isinstance(snapshot_data, dict) else []
        )

        parsed_nodes: list[Node] = []
        for item in raw_nodes:
            if isinstance(item, dict):
                parsed_nodes.append(Node.from_state(item))

        parsed_connections: list[Connection] = []
        for item in raw_connections:
            if isinstance(item, dict):
                parsed_connections.append(Connection.from_state(item))

        audit_reason = (
            reason
            if reason is not None
            else payload.reason if payload.reason is not None
            else f"load graph snapshot: {name}"
        )
        self._replace_graph_content(
            owner_id=normalized_owner,
            parsed_nodes=parsed_nodes,
            parsed_connections=parsed_connections,
            actor=actor,
            clear_reason=f"{audit_reason} [clear existing graph]",
            create_reason=f"{audit_reason} [restore snapshot]",
        )

        loaded_snapshot = self.graph_snapshot(normalized_owner)
        return GraphLoadResult(
            name=name,
            loaded_at=utc_now(),
            message="graph snapshot loaded",
            snapshot=loaded_snapshot,
        )

    def import_graph(
        self,
        owner_id: str,
        payload: GraphImportPayload,
        actor: str,
        reason: str | None = None,
    ) -> GraphImportResult:
        normalized_owner = self._owner(owner_id)
        if not payload.has_graph_data:
            raise ValueError("import payload must contain `nodes` or `connections` fields.")

        parsed_nodes = [Node.from_state(item) for item in payload.nodes]
        parsed_connections = [Connection.from_state(item) for item in payload.connections]

        audit_reason = (
            reason
            if reason is not None
            else payload.reason if payload.reason is not None
            else "import graph payload"
        )

        restored_nodes, restored_connections = self._replace_graph_content(
            owner_id=normalized_owner,
            parsed_nodes=parsed_nodes,
            parsed_connections=parsed_connections,
            actor=actor,
            clear_reason=f"{audit_reason} [clear existing graph]",
            create_reason=f"{audit_reason} [import payload]",
        )

        return GraphImportResult(
            node_count=restored_nodes,
            connection_count=restored_connections,
            imported_at=utc_now(),
            message="graph imported",
        )

    def _replace_graph_content(
        self,
        *,
        owner_id: str,
        parsed_nodes: list[Node],
        parsed_connections: list[Connection],
        actor: str,
        clear_reason: str,
        create_reason: str,
    ) -> tuple[int, int]:
        normalized_owner = self._owner(owner_id)
        now = utc_now()
        restored_node_count = 0
        restored_connection_count = 0

        with self.repository.transaction() as conn:
            active_connections = conn.execute(
                "SELECT * FROM connections WHERE owner_id = ? AND is_deleted = 0",
                (normalized_owner,),
            ).fetchall()
            for row_item in active_connections:
                existing = self._row_to_connection(row_item)
                before_state = existing.to_state()
                existing.is_deleted = True
                existing.version += 1
                existing.updated_at = now
                conn.execute(
                    """
                    UPDATE connections
                    SET is_deleted = 1, version = ?, updated_at = ?
                    WHERE owner_id = ? AND id = ?
                    """,
                    (existing.version, existing.updated_at, normalized_owner, existing.id),
                )
                self._insert_audit(
                    conn,
                    normalized_owner,
                    AuditLog(
                        entity_type=EntityType.CONNECTION.value,
                        entity_id=existing.id,
                        action=AuditAction.DELETE.value,
                        actor=actor,
                        reason=clear_reason,
                        before_state=before_state,
                        after_state=existing.to_state(),
                    ),
                )

            active_nodes = conn.execute(
                "SELECT * FROM nodes WHERE owner_id = ? AND is_deleted = 0",
                (normalized_owner,),
            ).fetchall()
            for row_item in active_nodes:
                existing = self._row_to_node(row_item)
                before_state = existing.to_state()
                existing.is_deleted = True
                existing.version += 1
                existing.updated_at = now
                conn.execute(
                    """
                    UPDATE nodes
                    SET is_deleted = 1, version = ?, updated_at = ?
                    WHERE owner_id = ? AND id = ?
                    """,
                    (existing.version, existing.updated_at, normalized_owner, existing.id),
                )
                self._insert_audit(
                    conn,
                    normalized_owner,
                    AuditLog(
                        entity_type=EntityType.NODE.value,
                        entity_id=existing.id,
                        action=AuditAction.DELETE.value,
                        actor=actor,
                        reason=clear_reason,
                        before_state=before_state,
                        after_state=existing.to_state(),
                    ),
                )

            node_id_map: dict[str, str] = {}
            for source_node in parsed_nodes:
                restored = Node.from_state(source_node.to_state())
                original_id = restored.id
                restored.id = str(uuid.uuid4())
                restored.created_at = now
                restored.updated_at = now
                restored.version = 1
                restored.is_deleted = False
                node_id_map[original_id] = restored.id

                conn.execute(
                    """
                    INSERT INTO nodes (
                        id, owner_id, content, summary,
                        position_x, position_y,
                        color, size, tags,
                        confidence, evidence,
                        created_at, updated_at,
                        version, is_deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        restored.id,
                        normalized_owner,
                        restored.content,
                        restored.summary,
                        restored.position.x,
                        restored.position.y,
                        restored.color,
                        restored.size,
                        json.dumps(restored.tags, ensure_ascii=False),
                        restored.confidence,
                        json.dumps(restored.evidence, ensure_ascii=False),
                        restored.created_at,
                        restored.updated_at,
                        restored.version,
                        int(restored.is_deleted),
                    ),
                )
                self._insert_audit(
                    conn,
                    normalized_owner,
                    AuditLog(
                        entity_type=EntityType.NODE.value,
                        entity_id=restored.id,
                        action=AuditAction.CREATE.value,
                        actor=actor,
                        reason=create_reason,
                        after_state=restored.to_state(),
                    ),
                )
                restored_node_count += 1

            for source_conn in parsed_connections:
                if source_conn.source_id not in node_id_map or source_conn.target_id not in node_id_map:
                    continue

                restored = Connection.from_state(source_conn.to_state())
                restored.id = str(uuid.uuid4())
                restored.source_id = node_id_map[source_conn.source_id]
                restored.target_id = node_id_map[source_conn.target_id]
                if restored.source_id == restored.target_id:
                    continue
                restored.created_at = now
                restored.updated_at = now
                restored.version = 1
                restored.is_deleted = False

                conn.execute(
                    """
                    INSERT INTO connections (
                        id, owner_id, source_id, target_id,
                        conn_type, description, strength,
                        created_at, updated_at,
                        version, is_deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        restored.id,
                        normalized_owner,
                        restored.source_id,
                        restored.target_id,
                        restored.conn_type,
                        restored.description,
                        restored.strength,
                        restored.created_at,
                        restored.updated_at,
                        restored.version,
                        int(restored.is_deleted),
                    ),
                )
                self._insert_audit(
                    conn,
                    normalized_owner,
                    AuditLog(
                        entity_type=EntityType.CONNECTION.value,
                        entity_id=restored.id,
                        action=AuditAction.CREATE.value,
                        actor=actor,
                        reason=create_reason,
                        after_state=restored.to_state(),
                    ),
                )
                restored_connection_count += 1

        return restored_node_count, restored_connection_count

    def delete_saved_graph(
        self,
        owner_id: str,
        payload: GraphDeletePayload,
        actor: str,
        reason: str | None = None,
    ) -> GraphDeleteResult:
        normalized_owner = self._owner(owner_id)
        name = self._normalize_snapshot_name(payload.name)
        deleted_at = utc_now()

        with self.repository.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM graph_snapshots WHERE owner_id = ? AND name = ?",
                (normalized_owner, name),
            )
            if int(cursor.rowcount) <= 0:
                raise ValueError("saved graph not found")

        return GraphDeleteResult(
            name=name,
            deleted_at=deleted_at,
            message="saved graph deleted",
        )

    def clear_graph(
        self,
        owner_id: str,
        payload: GraphClearPayload | None,
        actor: str,
        reason: str | None = None,
    ) -> GraphClearResult:
        normalized_owner = self._owner(owner_id)
        payload_reason = payload.reason if payload is not None else None
        audit_reason = (
            reason
            if reason is not None
            else payload_reason if payload_reason is not None
            else "clear current graph"
        )
        clear_reason = f"{audit_reason} [clear existing graph]"
        now = utc_now()

        cleared_connections = 0
        cleared_nodes = 0

        with self.repository.transaction() as conn:
            active_connections = conn.execute(
                "SELECT * FROM connections WHERE owner_id = ? AND is_deleted = 0",
                (normalized_owner,),
            ).fetchall()
            for row_item in active_connections:
                existing = self._row_to_connection(row_item)
                before_state = existing.to_state()
                existing.is_deleted = True
                existing.version += 1
                existing.updated_at = now

                conn.execute(
                    """
                    UPDATE connections
                    SET is_deleted = 1, version = ?, updated_at = ?
                    WHERE owner_id = ? AND id = ?
                    """,
                    (existing.version, existing.updated_at, normalized_owner, existing.id),
                )
                self._insert_audit(
                    conn,
                    normalized_owner,
                    AuditLog(
                        entity_type=EntityType.CONNECTION.value,
                        entity_id=existing.id,
                        action=AuditAction.DELETE.value,
                        actor=actor,
                        reason=clear_reason,
                        before_state=before_state,
                        after_state=existing.to_state(),
                    ),
                )
                cleared_connections += 1

            active_nodes = conn.execute(
                "SELECT * FROM nodes WHERE owner_id = ? AND is_deleted = 0",
                (normalized_owner,),
            ).fetchall()
            for row_item in active_nodes:
                existing = self._row_to_node(row_item)
                before_state = existing.to_state()
                existing.is_deleted = True
                existing.version += 1
                existing.updated_at = now

                conn.execute(
                    """
                    UPDATE nodes
                    SET is_deleted = 1, version = ?, updated_at = ?
                    WHERE owner_id = ? AND id = ?
                    """,
                    (existing.version, existing.updated_at, normalized_owner, existing.id),
                )
                self._insert_audit(
                    conn,
                    normalized_owner,
                    AuditLog(
                        entity_type=EntityType.NODE.value,
                        entity_id=existing.id,
                        action=AuditAction.DELETE.value,
                        actor=actor,
                        reason=clear_reason,
                        before_state=before_state,
                        after_state=existing.to_state(),
                    ),
                )
                cleared_nodes += 1

        return GraphClearResult(
            cleared_nodes=cleared_nodes,
            cleared_connections=cleared_connections,
            cleared_at=utc_now(),
            message="current graph cleared",
        )

    def list_audits(self, owner_id: str, query: AuditQuery) -> list[AuditRecord]:
        normalized_owner = self._owner(owner_id)
        sql = "SELECT * FROM audits WHERE owner_id = ?"
        params: list[object] = [normalized_owner]

        if query.entity_type:
            sql += " AND entity_type = ?"
            params.append(query.entity_type)
        if query.entity_id:
            sql += " AND entity_id = ?"
            params.append(query.entity_id)

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(min(max(int(query.limit), 1), 1000))

        rows = self.repository.fetch_all(sql, params)
        return [
            AuditRecord(
                id=int(row["id"]),
                entity_type=str(row["entity_type"]),
                entity_id=str(row["entity_id"]),
                action=str(row["action"]),
                actor=str(row["actor"]),
                reason=str(row["reason"]) if row["reason"] is not None else None,
                before_state=_safe_json_loads(row["before_state"], None),
                after_state=_safe_json_loads(row["after_state"], None),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def export_audits(self, owner_id: str, query: AuditQuery) -> AuditExportResult:
        normalized_query = AuditQuery(
            entity_type=(query.entity_type or None),
            entity_id=(query.entity_id or None),
            limit=min(max(int(query.limit), 1), 5000),
        )
        audits = self.list_audits(owner_id, normalized_query)

        entity_counts: dict[str, int] = {}
        action_counts: dict[str, int] = {}
        actor_counts: dict[str, int] = {}

        for record in audits:
            entity_counts[record.entity_type] = entity_counts.get(record.entity_type, 0) + 1
            action_counts[record.action] = action_counts.get(record.action, 0) + 1
            actor_counts[record.actor] = actor_counts.get(record.actor, 0) + 1

        exported_at = utc_now()
        safe_stamp = (
            exported_at.replace(":", "-")
            .replace(".", "-")
            .replace("+", "p")
        )
        file_name = f"thinking-graph-audit-report-{safe_stamp}.json"

        return AuditExportResult(
            format="thinking-graph-audit-report-v1",
            exported_at=exported_at,
            record_count=len(audits),
            entity_counts=entity_counts,
            action_counts=action_counts,
            actor_counts=actor_counts,
            suggested_file_name=file_name,
            audits=audits,
        )

    def verify_audit_integrity(self, owner_id: str) -> AuditIntegrityReport:
        normalized_owner = self._owner(owner_id)
        issues: list[str] = []

        entity_table_pairs = (
            (EntityType.NODE.value, "nodes"),
            (EntityType.CONNECTION.value, "connections"),
        )

        for entity_type, table in entity_table_pairs:
            records = self.repository.fetch_all(
                f"SELECT id, is_deleted FROM {table} WHERE owner_id = ?",
                (normalized_owner,),
            )
            for record in records:
                entity_id = str(record["id"])
                actions = self.repository.fetch_all(
                    """
                    SELECT action, before_state, after_state
                    FROM audits
                    WHERE owner_id = ? AND entity_type = ? AND entity_id = ?
                    """,
                    (normalized_owner, entity_type, entity_id),
                )
                action_names = {str(row["action"]) for row in actions}
                if AuditAction.CREATE.value not in action_names:
                    issues.append(f"{entity_type}:{entity_id} missing create audit.")
                if int(record["is_deleted"]) == 1 and AuditAction.DELETE.value not in action_names:
                    issues.append(f"{entity_type}:{entity_id} missing delete audit.")

                for action in actions:
                    action_name = str(action["action"])
                    if action_name == AuditAction.CREATE.value and not action["after_state"]:
                        issues.append(
                            f"{entity_type}:{entity_id} create audit missing after_state."
                        )
                    if action_name == AuditAction.UPDATE.value and (
                        not action["before_state"] or not action["after_state"]
                    ):
                        issues.append(
                            f"{entity_type}:{entity_id} update audit missing state snapshot."
                        )
                    if action_name == AuditAction.DELETE.value and not action["before_state"]:
                        issues.append(
                            f"{entity_type}:{entity_id} delete audit missing before_state."
                        )

        return AuditIntegrityReport(
            ok=(len(issues) == 0),
            issues=issues,
            checked_at=utc_now(),
        )

    @staticmethod
    def _normalize_snapshot_name(name: str) -> str:
        normalized = name.strip()
        if not normalized:
            raise ValueError("`name` is required.")
        if len(normalized) > 120:
            raise ValueError("`name` is too long (max 120 characters).")
        return normalized

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return min(max(value, low), high)

    @staticmethod
    def _insert_audit(conn: sqlite3.Connection, owner_id: str, log: AuditLog) -> None:
        conn.execute(
            """
            INSERT INTO audits (
                owner_id, entity_type, entity_id, action,
                actor, reason,
                before_state, after_state,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                owner_id,
                log.entity_type,
                log.entity_id,
                log.action,
                log.actor,
                log.reason,
                json.dumps(log.before_state, ensure_ascii=False) if log.before_state else None,
                json.dumps(log.after_state, ensure_ascii=False) if log.after_state else None,
                log.timestamp,
            ),
        )

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> Node:
        tags = _safe_json_loads(row["tags"], [])
        evidence = _safe_json_loads(row["evidence"], [])

        tags_list = [str(item) for item in tags] if isinstance(tags, list) else []
        evidence_list = [str(item) for item in evidence] if isinstance(evidence, list) else []

        return Node.from_state(
            {
                "id": str(row["id"]),
                "content": str(row["content"]),
                "summary": str(row["summary"]),
                "position": {
                    "x": float(row["position_x"]),
                    "y": float(row["position_y"]),
                },
                "color": str(row["color"]),
                "size": float(row["size"]),
                "tags": tags_list,
                "confidence": float(row["confidence"]),
                "evidence": evidence_list,
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "version": int(row["version"]),
                "is_deleted": bool(row["is_deleted"]),
            }
        )

    @staticmethod
    def _row_to_connection(row: sqlite3.Row) -> Connection:
        return Connection.from_state(
            {
                "id": str(row["id"]),
                "source_id": str(row["source_id"]),
                "target_id": str(row["target_id"]),
                "conn_type": str(row["conn_type"]),
                "description": str(row["description"]),
                "strength": float(row["strength"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "version": int(row["version"]),
                "is_deleted": bool(row["is_deleted"]),
            }
        )
