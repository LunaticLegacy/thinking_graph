"""Smoke tests for basic imports and startup."""

from __future__ import annotations


class TestImports:
    """Test that all modules can be imported."""

    def test_import_config(self):
        """Should import config module."""
        from config import RuntimeConfig, ServerConfig, PathsConfig, DatabaseConfig, LLMConfig
        assert RuntimeConfig is not None

    def test_import_backend(self):
        """Should import backend module."""
        from backend import SQLiteRepository
        from backend.services import GraphService, LLMService
        assert SQLiteRepository is not None
        assert GraphService is not None
        assert LLMService is not None

    def test_import_datamodels(self):
        """Should import datamodels."""
        from datamodels.graph_models import Node, Connection, NodeCreatePayload
        from datamodels.ai_llm_models import LLMChatRequest
        assert Node is not None
        assert Connection is not None

    def test_import_core(self):
        """Should import core modules."""
        from core.graph import Node, Connection
        from core.visualization import build_vis_payload
        assert Node is not None
        assert Connection is not None
        assert build_vis_payload is not None

    def test_import_web(self):
        """Should import web module."""
        from web import create_app
        assert create_app is not None

    def test_main_entry_point(self):
        """Should be able to import main module."""
        import main
        assert main is not None
