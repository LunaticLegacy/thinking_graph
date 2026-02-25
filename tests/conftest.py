"""Pytest fixtures and configuration for Thinking Graph tests."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend import SQLiteRepository
from backend.services import GraphService, LLMService
from config import RuntimeConfig, LLMConfig
from datamodels.graph_models import (
    NodeCreatePayload,
    Position,
    ConnectionCreatePayload,
    ConnectionType,
)


@pytest.fixture
def temp_db_path() -> str:
    """Provide a temporary database file path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def repository(temp_db_path: str) -> SQLiteRepository:
    """Create a fresh SQLiteRepository for each test."""
    return SQLiteRepository(db_path=temp_db_path)


@pytest.fixture
def graph_service(repository: SQLiteRepository) -> GraphService:
    """Create a GraphService with a fresh repository."""
    return GraphService(repository)


@pytest.fixture
def sample_node_payload() -> NodeCreatePayload:
    """Return a sample node creation payload."""
    return NodeCreatePayload(
        content="Test node content",
        summary="Test summary",
        position=Position(x=100.0, y=200.0),
        color="#ff0000",
        size=1.5,
        tags=["test", "sample"],
        confidence=0.8,
        evidence=["source1"],
    )


@pytest.fixture
def sample_connection_payload() -> ConnectionCreatePayload:
    """Return a sample connection creation payload."""
    return ConnectionCreatePayload(
        source_id="node_1",
        target_id="node_2",
        conn_type=ConnectionType.SUPPORTS,
        description="Test connection",
        strength=0.9,
    )


@pytest.fixture
def mock_llm_config() -> LLMConfig:
    """Return a mock LLM config for testing."""
    return LLMConfig(
        backend="remote_api",
        remote_api={"api_key": "test-key", "base_url": "https://test.api", "model": "test-model"},
        local_api={"api_key": "", "base_url": "", "model": ""},
        local_runtime={"model": "", "model_dir": "", "npu_device": "", "require_npu": False, "onnx_provider": ""},
    )


@pytest.fixture
def app_config(temp_db_path: str):
    """Create a test runtime config."""
    from config import RuntimeConfig, ServerConfig, PathsConfig, DatabaseConfig
    
    return RuntimeConfig(
        server=ServerConfig(host="127.0.0.1", port=5001, debug=True, enable_cors=True),
        paths=PathsConfig(
            template_dir="templates",
            static_dir="static",
            data_dir="data",
            project_db_path=temp_db_path,
            default_db_path=temp_db_path,
        ),
        database=DatabaseConfig(db_path=temp_db_path),
        llm=mock_llm_config(),
    )
