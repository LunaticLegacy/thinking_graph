"""SQLite repository for Thinking Graph persistence."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence
import sqlite3


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
                    name TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    node_count INTEGER NOT NULL DEFAULT 0,
                    connection_count INTEGER NOT NULL DEFAULT 0,
                    actor TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_connections_source
                    ON connections(source_id);
                CREATE INDEX IF NOT EXISTS idx_connections_target
                    ON connections(target_id);
                CREATE INDEX IF NOT EXISTS idx_audits_entity
                    ON audits(entity_type, entity_id);
                CREATE INDEX IF NOT EXISTS idx_audits_created_at
                    ON audits(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_snapshots_saved_at
                    ON graph_snapshots(saved_at DESC);
                """
            )

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
