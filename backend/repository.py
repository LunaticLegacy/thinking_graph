"""SQLite repository for Thinking Graph persistence."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence
import sqlite3


LEGACY_OWNER_ID = "legacy-single-user"


class SQLiteRepository:
    """A lightweight transactional repository."""

    def __init__(self, db_path: str = "data/thinking_graph.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL DEFAULT 'legacy-single-user',
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    position_x REAL NOT NULL DEFAULT 0,
                    position_y REAL NOT NULL DEFAULT 0,
                    color TEXT NOT NULL DEFAULT '#157f83',
                    size REAL NOT NULL DEFAULT 1,
                    tags TEXT NOT NULL DEFAULT '[]',
                    confidence REAL NOT NULL DEFAULT 1,
                    evidence TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    is_deleted INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS connections (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL DEFAULT 'legacy-single-user',
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    conn_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    strength REAL NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    is_deleted INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (source_id) REFERENCES nodes(id),
                    FOREIGN KEY (target_id) REFERENCES nodes(id)
                );

                CREATE TABLE IF NOT EXISTS audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id TEXT NOT NULL DEFAULT 'legacy-single-user',
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT,
                    before_state TEXT,
                    after_state TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS graph_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id TEXT NOT NULL DEFAULT 'legacy-single-user',
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    node_count INTEGER NOT NULL DEFAULT 0,
                    connection_count INTEGER NOT NULL DEFAULT 0,
                    actor TEXT NOT NULL,
                    saved_at TEXT NOT NULL,
                    UNIQUE (owner_id, name)
                );
                """
            )
            self._migrate_schema(conn)
            self._ensure_indexes(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        self._ensure_owner_column(conn, "nodes")
        self._ensure_owner_column(conn, "connections")
        self._ensure_owner_column(conn, "audits")
        self._migrate_graph_snapshots_table(conn)

    def _ensure_owner_column(self, conn: sqlite3.Connection, table_name: str) -> None:
        columns = self._table_columns(conn, table_name)
        if "owner_id" in columns:
            return
        conn.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN owner_id TEXT NOT NULL DEFAULT '{LEGACY_OWNER_ID}'
            """
        )

    def _migrate_graph_snapshots_table(self, conn: sqlite3.Connection) -> None:
        columns = self._table_columns(conn, "graph_snapshots")
        if "owner_id" in columns and "id" in columns:
            return

        conn.execute("ALTER TABLE graph_snapshots RENAME TO graph_snapshots_legacy")
        conn.execute(
            """
            CREATE TABLE graph_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id TEXT NOT NULL DEFAULT 'legacy-single-user',
                name TEXT NOT NULL,
                payload TEXT NOT NULL,
                node_count INTEGER NOT NULL DEFAULT 0,
                connection_count INTEGER NOT NULL DEFAULT 0,
                actor TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                UNIQUE (owner_id, name)
            )
            """
        )

        legacy_columns = self._table_columns(conn, "graph_snapshots_legacy")
        if "owner_id" in legacy_columns:
            conn.execute(
                """
                INSERT INTO graph_snapshots (
                    owner_id, name, payload, node_count, connection_count, actor, saved_at
                )
                SELECT owner_id, name, payload, node_count, connection_count, actor, saved_at
                FROM graph_snapshots_legacy
                """
            )
        else:
            conn.execute(
                """
                INSERT INTO graph_snapshots (
                    owner_id, name, payload, node_count, connection_count, actor, saved_at
                )
                SELECT ?, name, payload, node_count, connection_count, actor, saved_at
                FROM graph_snapshots_legacy
                """,
                (LEGACY_OWNER_ID,),
            )

        conn.execute("DROP TABLE graph_snapshots_legacy")

    def _ensure_indexes(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_nodes_owner_created_at
                ON nodes(owner_id, created_at ASC);
            CREATE INDEX IF NOT EXISTS idx_connections_source
                ON connections(source_id);
            CREATE INDEX IF NOT EXISTS idx_connections_target
                ON connections(target_id);
            CREATE INDEX IF NOT EXISTS idx_connections_owner_source
                ON connections(owner_id, source_id);
            CREATE INDEX IF NOT EXISTS idx_connections_owner_target
                ON connections(owner_id, target_id);
            CREATE INDEX IF NOT EXISTS idx_connections_owner_created_at
                ON connections(owner_id, created_at ASC);
            CREATE INDEX IF NOT EXISTS idx_audits_entity
                ON audits(entity_type, entity_id);
            CREATE INDEX IF NOT EXISTS idx_audits_created_at
                ON audits(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_audits_owner_created_at
                ON audits(owner_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_snapshots_saved_at
                ON graph_snapshots(saved_at DESC);
            CREATE INDEX IF NOT EXISTS idx_snapshots_owner_saved_at
                ON graph_snapshots(owner_id, saved_at DESC);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_graph_snapshots_owner_name
                ON graph_snapshots(owner_id, name);
            """
        )

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fetch_one(self, query: str, params: Sequence[object] = ()) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(query, params).fetchone()

    def fetch_all(self, query: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(query, params).fetchall()
