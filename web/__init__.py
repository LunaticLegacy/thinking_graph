"""Flask app factory."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sqlite3
import tempfile

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover
    CORS = None

from backend import SQLiteRepository
from backend.services import GraphService, LLMService
from config import RuntimeConfig
from web.routes import web_bp


def _build_repository_with_fallback(db_path: str, *, allow_fallback: bool) -> SQLiteRepository:
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
        if not allow_fallback:
            raise
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


def _apply_security_settings(app: Flask, config: RuntimeConfig) -> None:
    app.secret_key = config.auth.secret_key
    app.config["SECRET_KEY"] = config.auth.secret_key
    app.config["SESSION_COOKIE_NAME"] = config.auth.session_cookie_name
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = config.auth.session_cookie_secure
    app.config["SESSION_COOKIE_SAMESITE"] = config.auth.session_cookie_samesite
    app.config["SESSION_COOKIE_DOMAIN"] = config.auth.session_cookie_domain
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=config.auth.permanent_session_days)


def _validate_runtime_security(config: RuntimeConfig) -> None:
    insecure_secrets = {"", "dev-insecure-change-me", "change-this-in-production"}
    if not config.server.debug and config.auth.secret_key in insecure_secrets:
        raise RuntimeError(
            "THINKING_GRAPH_SECRET_KEY must be set to a strong value before production deployment."
        )
    if (
        config.auth.session_cookie_samesite == "None"
        and not config.auth.session_cookie_secure
    ):
        raise RuntimeError("SESSION_COOKIE_SAMESITE=None requires session_cookie_secure=true.")


def create_app(runtime_config: RuntimeConfig | None = None) -> Flask:
    config = runtime_config or RuntimeConfig.load()
    _validate_runtime_security(config)

    app = Flask(
        __name__,
        template_folder=config.paths.template_dir,
        static_folder=config.paths.static_dir,
    )
    _apply_security_settings(app, config)

    if config.server.trusted_proxy_hops > 0:
        app.wsgi_app = ProxyFix(  # type: ignore[assignment]
            app.wsgi_app,
            x_for=config.server.trusted_proxy_hops,
            x_proto=config.server.trusted_proxy_hops,
            x_host=config.server.trusted_proxy_hops,
            x_port=config.server.trusted_proxy_hops,
        )

    if CORS is not None and config.server.enable_cors:
        CORS(app, supports_credentials=True)

    repository = _build_repository_with_fallback(
        config.database.db_path,
        allow_fallback=(config.server.allow_db_fallback or config.server.debug),
    )
    if str(repository.db_path) != str(config.database.db_path):
        config.database.db_path = str(repository.db_path)

    app.extensions["runtime_config"] = config
    app.extensions["graph_service"] = GraphService(repository)
    app.extensions["llm_service"] = LLMService(config.llm)

    app.register_blueprint(web_bp)
    return app
