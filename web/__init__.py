"""Flask app factory."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile

from flask import Flask

try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover
    CORS = None

from backend import SQLiteRepository
from backend.services import GraphService, LLMService
from config import RuntimeConfig
from web.routes import web_bp


def _build_repository_with_fallback(db_path: str) -> SQLiteRepository:
    try:
        repository = SQLiteRepository(db_path=db_path)
        with repository.transaction() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS _repo_healthcheck (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO _repo_healthcheck (key, value)
                VALUES ('write_probe', 'ok')
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """
            )
        return repository
    except (sqlite3.OperationalError, OSError):
        fallback_db = str(Path(tempfile.gettempdir()) / "thinking_graph.db")
        repository = SQLiteRepository(db_path=fallback_db)
        with repository.transaction() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS _repo_healthcheck (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO _repo_healthcheck (key, value)
                VALUES ('write_probe', 'ok')
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """
            )
        return repository


def create_app(runtime_config: RuntimeConfig | None = None) -> Flask:
    config = runtime_config or RuntimeConfig.load()

    app = Flask(
        __name__,
        template_folder=config.paths.template_dir,
        static_folder=config.paths.static_dir,
    )

    if CORS is not None and config.server.enable_cors:
        CORS(app)

    repository = _build_repository_with_fallback(config.database.db_path)
    if str(repository.db_path) != str(config.database.db_path):
        config.database.db_path = str(repository.db_path)

    app.extensions["runtime_config"] = config
    app.extensions["graph_service"] = GraphService(repository)
    app.extensions["llm_service"] = LLMService(config.llm)

    app.register_blueprint(web_bp)
    return app
