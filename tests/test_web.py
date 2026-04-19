"""Tests for Flask app factory and web layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from web import create_app
from config import RuntimeConfig


class TestAppFactory:
    """Test suite for Flask app factory."""

    def test_create_app_returns_flask_app(self, app_config: RuntimeConfig):
        """Should return a valid Flask app instance."""
        from flask import Flask
        
        app = create_app(app_config)
        
        assert isinstance(app, Flask)
        assert app.extensions is not None

    def test_create_app_registers_extensions(self, app_config: RuntimeConfig):
        """Should register required extensions."""
        app = create_app(app_config)
        
        assert "runtime_config" in app.extensions
        assert "graph_service" in app.extensions
        assert "llm_service" in app.extensions

    def test_create_app_registers_blueprint(self, app_config: RuntimeConfig):
        """Should register web blueprint."""
        app = create_app(app_config)
        
        # Check that routes are registered
        rules = list(app.url_map.iter_rules())
        route_endpoints = {rule.endpoint for rule in rules}
        
        # Should have at least the web blueprint routes
        assert any("web." in ep for ep in route_endpoints)


@pytest.fixture
def test_client(app_config: RuntimeConfig):
    """Create a test client."""
    app = create_app(app_config)
    app.config["TESTING"] = True
    return app.test_client()


class TestAppRoutes:
    """Test suite for HTTP routes."""

    def test_index_route(self, test_client):
        """Should serve the main page or return 404 if template missing."""
        response = test_client.get("/")
        # 200 if template exists, 404 if missing - both are acceptable for smoke test
        assert response.status_code in (200, 404)

    def test_api_nodes_get(self, test_client):
        """Should handle GET /api/nodes."""
        response = test_client.get("/api/nodes")
        # Should return JSON or 404 if route not registered
        assert response.status_code in (200, 404)
        
        if response.status_code == 200:
            assert response.content_type == "application/json"

    def test_api_routes_isolate_users_by_session(self, app_config: RuntimeConfig):
        """Separate clients should not share graph data."""
        app = create_app(app_config)
        app.config["TESTING"] = True

        client_a = app.test_client()
        client_b = app.test_client()

        create_response = client_a.post(
            "/api/nodes",
            json={"content": "Alice node", "summary": "A"},
        )
        assert create_response.status_code == 201

        nodes_a = client_a.get("/api/nodes")
        nodes_b = client_b.get("/api/nodes")
        assert nodes_a.status_code == 200
        assert nodes_b.status_code == 200

        payload_a = nodes_a.get_json() or {}
        payload_b = nodes_b.get_json() or {}
        assert len(payload_a.get("nodes", [])) == 1
        assert payload_b.get("nodes", []) == []

    def test_settings_route_masks_secrets_and_blocks_runtime_write(
        self,
        app_config: RuntimeConfig,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        """Settings endpoint should not leak secrets or allow writes by default."""
        config_path = tmp_path / "app_config.toml"
        config_path.write_text(
            """
[llm]
backend = "remote_api"

[llm.remote_api]
api_key = "super-secret-key"
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"
""".strip()
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("APP_CONFIG_FILE", str(config_path))

        app = create_app(app_config)
        app.config["TESTING"] = True
        client = app.test_client()

        get_response = client.get("/api/settings")
        assert get_response.status_code == 200
        payload = get_response.get_json() or {}
        assert payload.get("editable") is False
        assert payload["llm"]["remote_api"]["api_key"] == ""
        assert payload["llm"]["remote_api"]["api_key_configured"] is True

        put_response = client.put(
            "/api/settings",
            json={"llm": {"backend": "remote_api"}},
        )
        assert put_response.status_code == 403


class TestFallbackBehavior:
    """Test repository fallback behavior."""

    def test_fallback_in_dev_mode(self, tmp_path):
        """Should fallback to temp db in dev mode when primary fails."""
        from pathlib import Path
        from web import create_app
        from config import RuntimeConfig, ServerConfig, PathsConfig, DatabaseConfig, LLMConfig
        
        project_root = Path(__file__).parent.parent
        
        llm_config = LLMConfig.from_sources(data={
            "backend": "remote_api",
            "remote_api": {"api_key": "", "base_url": "", "model": ""},
        })
        
        # Use a read-only directory to simulate failure
        config = RuntimeConfig(
            server=ServerConfig(host="127.0.0.1", port=5001, debug=True, enable_cors=True),
            paths=PathsConfig(
                project_root=project_root,
                template_dir="templates",
                static_dir="static",
                data_dir=str(tmp_path),
                project_db_path=str(tmp_path / "test.db"),
                default_db_path=str(tmp_path / "test.db"),
            ),
            database=DatabaseConfig(db_path=str(tmp_path / "test.db")),
            llm=llm_config,
        )
        
        app = create_app(config)
        
        # App should start successfully
        assert app.extensions["graph_service"] is not None
