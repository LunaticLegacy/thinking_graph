"""Tests for SQLite repository layer."""

from __future__ import annotations

import sqlite3

import pytest

from backend import SQLiteRepository


class TestSQLiteRepository:
    """Test suite for SQLiteRepository."""

    def test_init_creates_schema(self, temp_db_path: str):
        """Repository initialization should create all tables."""
        repo = SQLiteRepository(db_path=temp_db_path)
        
        # Verify tables exist by querying them
        tables = repo.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = {row["name"] for row in tables}
        
        # Core tables created by repository (not _repo_healthcheck which is created by web app)
        expected_tables = {"nodes", "connections", "audits", "graph_snapshots"}
        assert expected_tables.issubset(table_names)

    def test_transaction_commit(self, repository: SQLiteRepository):
        """Transaction should commit successfully."""
        with repository.transaction() as conn:
            conn.execute(
                "INSERT INTO nodes (id, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("test-node-1", "Test content", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
            )
        
        # Verify the insert persisted
        result = repository.fetch_one(
            "SELECT * FROM nodes WHERE id = ?", ("test-node-1",)
        )
        assert result is not None
        assert result["content"] == "Test content"

    def test_transaction_rollback(self, repository: SQLiteRepository):
        """Transaction should rollback on exception."""
        try:
            with repository.transaction() as conn:
                conn.execute(
                    "INSERT INTO nodes (id, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    ("test-node-2", "Test content", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
                )
                raise ValueError("Intentional error")
        except ValueError:
            pass
        
        # Verify the insert was rolled back
        result = repository.fetch_one(
            "SELECT * FROM nodes WHERE id = ?", ("test-node-2",)
        )
        assert result is None

    def test_fetch_one_returns_none_when_not_found(self, repository: SQLiteRepository):
        """fetch_one should return None for non-existent records."""
        result = repository.fetch_one(
            "SELECT * FROM nodes WHERE id = ?", ("non-existent",)
        )
        assert result is None

    def test_fetch_all_returns_empty_list_when_no_results(self, repository: SQLiteRepository):
        """fetch_all should return empty list when no results."""
        results = repository.fetch_all(
            "SELECT * FROM nodes WHERE id = ?", ("non-existent",)
        )
        assert results == []

    def test_foreign_keys_enabled(self, repository: SQLiteRepository):
        """Foreign key constraints should be enabled."""
        # This should raise an integrity error due to foreign key constraint
        with pytest.raises(sqlite3.IntegrityError):
            with repository.transaction() as conn:
                conn.execute(
                    """INSERT INTO connections 
                       (id, source_id, target_id, conn_type, created_at, updated_at) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    ("conn-1", "non-existent-source", "non-existent-target", "supports", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
                )

    def test_indexes_created(self, repository: SQLiteRepository):
        """Required indexes should be created."""
        indexes = repository.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        index_names = {row["name"] for row in indexes}
        
        expected_indexes = {
            "idx_connections_source",
            "idx_connections_target",
            "idx_audits_entity",
            "idx_audits_created_at",
            "idx_snapshots_saved_at",
        }
        assert expected_indexes.issubset(index_names)
