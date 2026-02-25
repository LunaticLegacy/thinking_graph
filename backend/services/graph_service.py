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

    def list_nodes(self, include_deleted: bool = False) -> list[Node]:
        query = "SELECT * FROM nodes"
        if not include_deleted:
            query += " WHERE is_deleted = 0"
        query += " ORDER BY created_at ASC"
        rows = self.repository.fetch_all(query)
        return [self._row_to_node(row) for row in rows]

    def get_node(self, node_id: str) -> Node | None:
        row = self.repository.fetch_one(
            "SELECT * FROM nodes WHERE id = ? AND is_deleted = 0",
            (node_id,),
        )
        if not row:
            return None
        return self._row_to_node(row)

    def create_node(
        self,
        payload: NodeCreatePayload,
        actor: str,
        reason: str | None = None,
    ) -> Node:
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
                    id, content, summary,
                    position_x, position_y,
                    color, size, tags,
                    confidence, evidence,
                    created_at, updated_at,
                    version, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
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
        node_id: str,
        payload: NodeUpdatePayload,
        actor: str,
        reason: str | None = None,
    ) -> Node | None:
        row = self.repository.fetch_one("SELECT * FROM nodes WHERE id = ?", (node_id,))
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
                WHERE id = ?
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
                    node_id,
                ),
            )
            self._insert_audit(
                conn,
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
        node_id: str,
        actor: str,
        payload: DeletePayload | None = None,
        reason: str | None = None,
    ) -> bool:
        row = self.repository.fetch_one("SELECT * FROM nodes WHERE id = ?", (node_id,))
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
                WHERE id = ?
                """,
                (node.version, node.updated_at, node_id),
            )
            self._insert_audit(
                conn,
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
                WHERE is_deleted = 0 AND (source_id = ? OR target_id = ?)
                """,
                (node_id, node_id),
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
                    WHERE id = ?
                    """,
                    (edge.version, edge.updated_at, edge.id),
                )
                cascade_reason = (audit_reason or "") + " [cascade by node deletion]"
                self._insert_audit(
                    conn,
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

    def list_connections(self, include_deleted: bool = False) -> list[Connection]:
        query = "SELECT * FROM connections"
        if not include_deleted:
            query += " WHERE is_deleted = 0"
        query += " ORDER BY created_at ASC"
        rows = self.repository.fetch_all(query)
        return [self._row_to_connection(row) for row in rows]

    def create_connection(
        self,
        payload: ConnectionCreatePayload,
        actor: str,
        reason: str | None = None,
    ) -> Connection:
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
            "SELECT id FROM nodes WHERE id = ? AND is_deleted = 0",
            (source_id,),
        )
        target = self.repository.fetch_one(
            "SELECT id FROM nodes WHERE id = ? AND is_deleted = 0",
            (target_id,),
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
                    id, source_id, target_id,
                    conn_type, description, strength,
                    created_at, updated_at,
                    version, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
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
        conn_id: str,
        payload: ConnectionUpdatePayload,
        actor: str,
        reason: str | None = None,
    ) -> Connection | None:
        row = self.repository.fetch_one("SELECT * FROM connections WHERE id = ?", (conn_id,))
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
                WHERE id = ?
                """,
                (
                    updated.conn_type,
                    updated.description,
                    updated.strength,
                    updated.updated_at,
                    updated.version,
                    conn_id,
                ),
            )
            self._insert_audit(
                conn,
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
        conn_id: str,
        actor: str,
        payload: DeletePayload | None = None,
        reason: str | None = None,
    ) -> bool:
        row = self.repository.fetch_one("SELECT * FROM connections WHERE id = ?", (conn_id,))
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
                WHERE id = ?
                """,
                (edge.version, edge.updated_at, conn_id),
            )
            self._insert_audit(
                conn,
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

    def graph_snapshot(self) -> GraphSnapshot:
        node_rows = self.repository.fetch_all(
            "SELECT * FROM nodes WHERE is_deleted = 0 ORDER BY created_at ASC"
        )
        conn_rows = self.repository.fetch_all(
            "SELECT * FROM connections WHERE is_deleted = 0 ORDER BY created_at ASC"
        )

        nodes = [self._row_to_node(row) for row in node_rows]
        connections = [self._row_to_connection(row) for row in conn_rows]
        vis_payload = build_vis_payload(nodes, connections)

        return GraphSnapshot(
            nodes=nodes,
            connections=connections,
            visualization=vis_payload,
        )

    def export_graph(self) -> GraphExportResult:
        snapshot = self.graph_snapshot()
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
        payload: GraphSavePayload,
        actor: str,
        reason: str | None = None,
    ) -> GraphSaveResult:
        name = self._normalize_snapshot_name(payload.name)
        saved_at = utc_now()
        snapshot = self.graph_snapshot()
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
                    name, payload, node_count, connection_count, actor, saved_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    payload = excluded.payload,
                    node_count = excluded.node_count,
                    connection_count = excluded.connection_count,
                    actor = excluded.actor,
                    saved_at = excluded.saved_at
                """,
                (
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

    def list_saved_graphs(self) -> list[SavedGraphSummary]:
        rows = self.repository.fetch_all(
            """
            SELECT name, node_count, connection_count, actor, saved_at
            FROM graph_snapshots
            ORDER BY saved_at DESC
            """
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
        payload: GraphLoadPayload,
        actor: str,
        reason: str | None = None,
    ) -> GraphLoadResult:
        name = self._normalize_snapshot_name(payload.name)
        row = self.repository.fetch_one(
            "SELECT payload FROM graph_snapshots WHERE name = ?",
            (name,),
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
            parsed_nodes=parsed_nodes,
            parsed_connections=parsed_connections,
            actor=actor,
            clear_reason=f"{audit_reason} [clear existing graph]",
            create_reason=f"{audit_reason} [restore snapshot]",
        )

        loaded_snapshot = self.graph_snapshot()
        return GraphLoadResult(
            name=name,
            loaded_at=utc_now(),
            message="graph snapshot loaded",
            snapshot=loaded_snapshot,
        )

    def import_graph(
        self,
        payload: GraphImportPayload,
        actor: str,
        reason: str | None = None,
    ) -> GraphImportResult:
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
        parsed_nodes: list[Node],
        parsed_connections: list[Connection],
        actor: str,
        clear_reason: str,
        create_reason: str,
    ) -> tuple[int, int]:
        now = utc_now()
        restored_node_count = 0
        restored_connection_count = 0

        with self.repository.transaction() as conn:
            active_connections = conn.execute(
                "SELECT * FROM connections WHERE is_deleted = 0"
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
                    WHERE id = ?
                    """,
                    (existing.version, existing.updated_at, existing.id),
                )
                self._insert_audit(
                    conn,
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

            active_nodes = conn.execute("SELECT * FROM nodes WHERE is_deleted = 0").fetchall()
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
                    WHERE id = ?
                    """,
                    (existing.version, existing.updated_at, existing.id),
                )
                self._insert_audit(
                    conn,
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
                        id, content, summary,
                        position_x, position_y,
                        color, size, tags,
                        confidence, evidence,
                        created_at, updated_at,
                        version, is_deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        restored.id,
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
                        id, source_id, target_id,
                        conn_type, description, strength,
                        created_at, updated_at,
                        version, is_deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        restored.id,
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
        payload: GraphDeletePayload,
        actor: str,
        reason: str | None = None,
    ) -> GraphDeleteResult:
        name = self._normalize_snapshot_name(payload.name)
        deleted_at = utc_now()

        with self.repository.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM graph_snapshots WHERE name = ?",
                (name,),
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
        payload: GraphClearPayload | None,
        actor: str,
        reason: str | None = None,
    ) -> GraphClearResult:
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
                "SELECT * FROM connections WHERE is_deleted = 0"
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
                    WHERE id = ?
                    """,
                    (existing.version, existing.updated_at, existing.id),
                )
                self._insert_audit(
                    conn,
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

            active_nodes = conn.execute("SELECT * FROM nodes WHERE is_deleted = 0").fetchall()
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
                    WHERE id = ?
                    """,
                    (existing.version, existing.updated_at, existing.id),
                )
                self._insert_audit(
                    conn,
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

    def list_audits(self, query: AuditQuery) -> list[AuditRecord]:
        sql = "SELECT * FROM audits WHERE 1 = 1"
        params: list[object] = []

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

    def export_audits(self, query: AuditQuery) -> AuditExportResult:
        normalized_query = AuditQuery(
            entity_type=(query.entity_type or None),
            entity_id=(query.entity_id or None),
            limit=min(max(int(query.limit), 1), 5000),
        )
        audits = self.list_audits(normalized_query)

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

    def verify_audit_integrity(self) -> AuditIntegrityReport:
        issues: list[str] = []

        entity_table_pairs = (
            (EntityType.NODE.value, "nodes"),
            (EntityType.CONNECTION.value, "connections"),
        )

        for entity_type, table in entity_table_pairs:
            records = self.repository.fetch_all(f"SELECT id, is_deleted FROM {table}")
            for record in records:
                entity_id = str(record["id"])
                actions = self.repository.fetch_all(
                    """
                    SELECT action, before_state, after_state
                    FROM audits
                    WHERE entity_type = ? AND entity_id = ?
                    """,
                    (entity_type, entity_id),
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
    def _insert_audit(conn: sqlite3.Connection, log: AuditLog) -> None:
        conn.execute(
            """
            INSERT INTO audits (
                entity_type, entity_id, action,
                actor, reason,
                before_state, after_state,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
